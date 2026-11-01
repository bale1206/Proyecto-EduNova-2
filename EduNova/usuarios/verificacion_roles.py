"""Código OTP de seis dígitos para docentes y dirección de carrera.

Se usa una sesión vinculada a la cuenta pendiente, con cinco intentos,
10 minutos de vencimiento, un solo uso, reenvíos limitados y controles CSRF.
Una vez confirmado el correo, la cuenta se activa sin aprobación manual.
"""
import hashlib
import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import Usuario, VerificacionCorreoRol

SESSION_KEY_ROLES = 'edunova_personal_pendiente_v1'
CADUCIDAD = timedelta(minutes=10)
ESPERA_REENVIO = timedelta(seconds=60)
VENTANA_ENVIO = timedelta(hours=1)
MAX_INTENTOS = 5
MAX_ENVIOS_CUENTA = 3


class ErrorCorreoRol(Exception):
    pass


def _codigo_aleatorio():
    return f'{secrets.randbelow(1_000_000):06d}'


def _key(kind, value):
    return 'edunova:otp:personal:' + kind + ':' + hashlib.sha256(value.encode()).hexdigest()


def _limite_envio(request, email):
    ip = request.META.get('REMOTE_ADDR', 'desconocida')
    for key, limite in ((_key('ip', ip), 30), (_key('email', email.casefold()), 3)):
        if int(cache.get(key, 0)) >= limite:
            raise ErrorCorreoRol('Demasiadas solicitudes de códigos. Inténtalo más tarde.')


def _registrar_envio(request, email):
    ip = request.META.get('REMOTE_ADDR', 'desconocida')
    for key in (_key('ip', ip), _key('email', email.casefold())):
        if not cache.add(key, 1, timeout=3600):
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=3600)


def _comprobar_dominio(usuario):
    dominios = getattr(settings, 'EDUNOVA_ROLE_EMAIL_DOMAINS', {})
    esperado = dominios.get(usuario.rol)
    if not esperado or usuario.email.lower().rsplit('@', 1)[-1] != esperado:
        raise ErrorCorreoRol('El correo no corresponde al dominio permitido para este perfil.')


def _enviar_email(usuario, codigo):
    if settings.EMAIL_BACKEND not in (
        'django.core.mail.backends.smtp.EmailBackend',
        'django.core.mail.backends.locmem.EmailBackend',
    ):
        raise ErrorCorreoRol('Configura el envío de correo SMTP en EduNova.')
    nombre = 'docente' if usuario.rol == Usuario.Rol.DOCENTE else 'director de carrera'
    mensaje = EmailMessage(
        subject='[EduNova] Verifica tu registro académico',
        body=(f'Se solicitó crear una cuenta de {nombre} con esta dirección.\n\n'
              f'Tu código de verificación es: {codigo}\n\n'
              'Caduca en 10 minutos y admite cinco intentos.\n'
              'Si no solicitaste esta cuenta, ignora este mensaje.\n'
              'No compartas este código.'),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.email],
    )
    try:
        if mensaje.send(fail_silently=False) != 1:
            raise ErrorCorreoRol('El servidor no aceptó el correo.')
    except (smtplib.SMTPException, OSError, TimeoutError, ValueError, RuntimeError) as exc:
        raise ErrorCorreoRol('No se pudo enviar el código. Inténtalo más tarde.') from exc


def crear_verificacion_rol(request, usuario):
    """Solo para nuevas cuentas inactivas dentro de transaction.atomic()."""
    if usuario.is_active or usuario.rol not in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
        raise ErrorCorreoRol('El perfil no está pendiente de verificación.')
    _comprobar_dominio(usuario)
    _limite_envio(request, usuario.email)
    codigo = _codigo_aleatorio()
    ahora = timezone.now()
    VerificacionCorreoRol.objects.create(
        usuario=usuario, codigo_hash=make_password(codigo), enviado_en=ahora,
        vence_en=ahora + CADUCIDAD, intentos_restantes=MAX_INTENTOS,
        envios_ventana=1, inicio_ventana=ahora,
    )
    _enviar_email(usuario, codigo)
    _registrar_envio(request, usuario.email)


def _pendiente(request):
    pk = request.session.get(SESSION_KEY_ROLES)
    if not isinstance(pk, int):
        return None
    return Usuario.objects.filter(
        pk=pk, rol__in=[Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO],
        is_active=False,
    ).first()


def _contexto(usuario, *, error='', aviso=''):
    desafio = VerificacionCorreoRol.objects.filter(usuario=usuario).first()
    ahora = timezone.now()
    espera = max(0, int((desafio.enviado_en + ESPERA_REENVIO - ahora).total_seconds()) + 1) if desafio else 0
    return {
        'correo': usuario.email, 'rol': usuario.get_rol_display(),
        'error': error, 'aviso': aviso, 'espera_reenvio': espera,
        'intentos_restantes': desafio.intentos_restantes if desafio else 0,
        'vencido': not desafio or ahora >= desafio.vence_en,
    }


@never_cache
@require_http_methods(['GET', 'POST'])
def verificar_registro_rol(request):
    if request.user.is_authenticated:
        return redirect('usuarios:post_login_redirect')
    usuario = _pendiente(request)
    if usuario is None:
        request.session.pop(SESSION_KEY_ROLES, None)
        messages.info(request, 'No hay una verificación de personal pendiente en esta sesión.')
        return redirect('usuarios:registro')
    error, aviso = '', ''
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'verificar':
            codigo = request.POST.get('codigo', '').strip()
            with transaction.atomic():
                desafio = VerificacionCorreoRol.objects.select_for_update().get(usuario=usuario)
                ahora = timezone.now()
                if desafio.confirmado_en:
                    error = 'Este correo ya fue verificado.'
                elif ahora >= desafio.vence_en:
                    error = 'El código venció. Solicita uno nuevo.'
                elif desafio.intentos_restantes == 0:
                    error = 'Se agotaron los intentos. Solicita un código nuevo.'
                elif len(codigo) == 6 and codigo.isascii() and codigo.isdecimal() and check_password(codigo, desafio.codigo_hash):
                    desafio.confirmado_en = ahora
                    desafio.codigo_hash = ''
                    desafio.save(update_fields=['confirmado_en', 'codigo_hash'])
                    request.session.pop(SESSION_KEY_ROLES, None)
                    # La activación es atómica con la verificación del OTP:
                    # no se habilita la cuenta si el desafío no fue confirmado.
                    # La verificación del dominio no garantiza un cargo institucional.
                    Usuario.objects.filter(pk=usuario.pk, is_active=False).update(is_active=True)
                    messages.success(request,
                        '¡Correo confirmado! Tu cuenta está activa. Ya puedes iniciar sesión.')
                    return redirect('usuarios:login')
                else:
                    desafio.intentos_restantes -= 1
                    desafio.save(update_fields=['intentos_restantes'])
                    error = f'Código incorrecto. Intentos restantes: {desafio.intentos_restantes}.'
        elif accion == 'reenviar':
            with transaction.atomic():
                desafio = VerificacionCorreoRol.objects.select_for_update().get(usuario=usuario)
                ahora = timezone.now()
                if desafio.confirmado_en:
                    error = 'Este correo ya fue verificado.'
                elif ahora < desafio.enviado_en + ESPERA_REENVIO:
                    error = 'Espera 60 segundos antes de solicitar otro código.'
                else:
                    envios = desafio.envios_ventana if ahora < desafio.inicio_ventana + VENTANA_ENVIO else 0
                    if envios >= MAX_ENVIOS_CUENTA:
                        error = 'Alcanzaste el límite de tres envíos por hora.'
                    else:
                        try:
                            _comprobar_dominio(usuario)
                            _limite_envio(request, usuario.email)
                            codigo = _codigo_aleatorio()
                            _enviar_email(usuario, codigo)
                        except ErrorCorreoRol as exc:
                            error = str(exc)
                        else:
                            desafio.codigo_hash = make_password(codigo)
                            desafio.enviado_en = ahora
                            desafio.vence_en = ahora + CADUCIDAD
                            desafio.intentos_restantes = MAX_INTENTOS
                            desafio.inicio_ventana = desafio.inicio_ventana if envios else ahora
                            desafio.envios_ventana = envios + 1
                            desafio.save(update_fields=['codigo_hash', 'enviado_en', 'vence_en', 'intentos_restantes', 'inicio_ventana', 'envios_ventana'])
                            _registrar_envio(request, usuario.email)
                            aviso = 'Enviamos un nuevo código. Comprueba tu correo.'
        else:
            error = 'Acción no reconocida.'
    return render(request, 'usuarios/verificar_registro_rol.html', _contexto(usuario, error=error, aviso=aviso))
