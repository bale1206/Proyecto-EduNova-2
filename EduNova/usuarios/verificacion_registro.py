"""Confirmación del correo Duoc UC antes de activar cuentas de estudiantes.

No modifica ni elimina cuentas activas; el endpoint público sólo funciona para
una cuenta inactiva creada en la sesión de registro actual.
"""
import hashlib
import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import Usuario, VerificacionCorreoEstudiante

SESSION_KEY = 'edunova_estudiante_pendiente_v1'
CADUCIDAD = timedelta(minutes=10)
ESPERA_REENVIO = timedelta(seconds=60)
VENTANA_ENVIO = timedelta(hours=1)
MAX_INTENTOS = 5
MAX_ENVIOS_CUENTA = 3


class ErrorCorreoEstudiante(Exception):
    """Error esperado y seguro para mostrar en la interfaz."""


def _codigo_aleatorio():
    return f'{secrets.randbelow(1_000_000):06d}'


def _key(kind, value):
    digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
    return f'edunova:envio:estudiante:{kind}:{digest}'


def _limite_envio(request, email):
    """Cota adicional por origen/destino. Usar caché COMPARTIDA en producción."""
    ip = request.META.get('REMOTE_ADDR', 'desconocida')
    for key, limit in ((_key('ip', ip), 30), (_key('email', email), 3)):
        if int(cache.get(key, 0)) >= limit:
            raise ErrorCorreoEstudiante('Demasiadas solicitudes de códigos. Inténtalo más tarde.')


def _registrar_envio(request, email):
    ip = request.META.get('REMOTE_ADDR', 'desconocida')
    for key in (_key('ip', ip), _key('email', email)):
        if not cache.add(key, 1, timeout=3600):
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=3600)


def _enviar_email(email, codigo):
    backend = settings.EMAIL_BACKEND
    if backend not in (
        'django.core.mail.backends.smtp.EmailBackend',
        'django.core.mail.backends.locmem.EmailBackend',  # pruebas automatizadas
    ):
        raise ErrorCorreoEstudiante('El envío de correo de EduNova no está configurado. Contacta a soporte.')
    mensaje = EmailMessage(
        subject='[EduNova] Verifica tu cuenta de estudiante',
        body=(
            'Se solicitó crear una cuenta de estudiante en EduNova con este correo.\n\n'
            f'Tu código de verificación es: {codigo}\n\n'
            'Caduca en 10 minutos y admite cinco intentos.\n'
            'No compartas este código con otras personas.\n'
            'Si no solicitaste esta cuenta, ignora este mensaje.\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    try:
        if mensaje.send(fail_silently=False) != 1:
            raise ErrorCorreoEstudiante('El servicio de correo no aceptó el mensaje.')
    except (smtplib.SMTPException, OSError, TimeoutError, ValueError, RuntimeError) as exc:
        raise ErrorCorreoEstudiante('No se pudo enviar el código. Inténtalo de nuevo más tarde.') from exc


def crear_verificacion(request, usuario):
    """Invocar DENTRO de la transacción del nuevo registro estudiantil."""
    if usuario.rol != Usuario.Rol.ESTUDIANTE or usuario.is_active:
        raise ErrorCorreoEstudiante('No es una cuenta estudiantil pendiente.')
    _limite_envio(request, usuario.email)
    codigo = _codigo_aleatorio()
    ahora = timezone.now()
    VerificacionCorreoEstudiante.objects.create(
        usuario=usuario,
        codigo_hash=make_password(codigo),
        enviado_en=ahora,
        vence_en=ahora + CADUCIDAD,
        intentos_restantes=MAX_INTENTOS,
        envios_ventana=1,
        inicio_ventana=ahora,
    )
    _enviar_email(usuario.email, codigo)
    _registrar_envio(request, usuario.email)


def _pendiente(request):
    pk = request.session.get(SESSION_KEY)
    if not isinstance(pk, int):
        return None
    return Usuario.objects.filter(
        pk=pk, rol=Usuario.Rol.ESTUDIANTE, is_active=False,
    ).first()


def _contexto(usuario, *, error='', aviso=''):
    desafio = VerificacionCorreoEstudiante.objects.filter(usuario=usuario).first()
    ahora = timezone.now()
    espera = 0
    if desafio:
        espera = max(0, int((desafio.enviado_en + ESPERA_REENVIO - ahora).total_seconds()) + 1)
    return {
        'correo': usuario.email,
        'error': error,
        'aviso': aviso,
        'espera_reenvio': espera,
        'intentos_restantes': desafio.intentos_restantes if desafio else 0,
        'vencido': not desafio or ahora >= desafio.vence_en,
    }


@never_cache
@require_http_methods(['GET', 'POST'])
def verificar_registro_estudiante(request):
    """Solo verifica la cuenta pendiente creada en esta sesión anónima."""
    if request.user.is_authenticated:
        return redirect('usuarios:post_login_redirect')
    usuario = _pendiente(request)
    if usuario is None:
        request.session.pop(SESSION_KEY, None)
        messages.info(request, 'No hay un registro estudiantil pendiente en esta sesión.')
        return redirect('usuarios:registro')

    error, aviso = '', ''
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'verificar':
            codigo = request.POST.get('codigo', '').strip()
            with transaction.atomic():
                desafio = VerificacionCorreoEstudiante.objects.select_for_update().get(usuario=usuario)
                ahora = timezone.now()
                if desafio.confirmado_en or usuario.is_active:
                    error = 'Esta cuenta ya fue verificada.'
                elif ahora >= desafio.vence_en:
                    error = 'El código venció. Solicita uno nuevo.'
                elif desafio.intentos_restantes == 0:
                    error = 'Se agotaron los intentos. Solicita un código nuevo.'
                elif len(codigo) == 6 and codigo.isascii() and codigo.isdecimal() and check_password(codigo, desafio.codigo_hash):
                    desafio.confirmado_en = ahora
                    desafio.codigo_hash = ''  # no conservar hashes después del uso
                    desafio.save(update_fields=['confirmado_en', 'codigo_hash'])
                    Usuario.objects.filter(pk=usuario.pk, is_active=False).update(is_active=True)
                    usuario.is_active = True
                    request.session.pop(SESSION_KEY, None)
                    # Comportamiento de login existente: tras el alta, entrar al portal.
                    login(request, usuario)
                    messages.success(request, 'Tu correo fue verificado. ¡Bienvenido a EduNova!')
                    return redirect('usuarios:post_login_redirect')
                else:
                    desafio.intentos_restantes -= 1
                    desafio.save(update_fields=['intentos_restantes'])
                    error = ('Código incorrecto. Intentos restantes: '
                             f'{desafio.intentos_restantes}.')
        elif accion == 'reenviar':
            with transaction.atomic():
                desafio = VerificacionCorreoEstudiante.objects.select_for_update().get(usuario=usuario)
                ahora = timezone.now()
                if ahora < desafio.enviado_en + ESPERA_REENVIO:
                    error = 'Espera 60 segundos antes de solicitar otro código.'
                else:
                    inicio = desafio.inicio_ventana
                    envios = desafio.envios_ventana if ahora < inicio + VENTANA_ENVIO else 0
                    if envios >= MAX_ENVIOS_CUENTA:
                        error = 'Alcanzaste el límite de envíos. Inténtalo después de una hora.'
                    else:
                        try:
                            _limite_envio(request, usuario.email)
                            codigo = _codigo_aleatorio()
                            # No invalidar el código anterior si el envío nuevo falla.
                            _enviar_email(usuario.email, codigo)
                        except ErrorCorreoEstudiante as exc:
                            error = str(exc)
                        else:
                            desafio.codigo_hash = make_password(codigo)
                            desafio.enviado_en = ahora
                            desafio.vence_en = ahora + CADUCIDAD
                            desafio.intentos_restantes = MAX_INTENTOS
                            desafio.inicio_ventana = inicio if envios else ahora
                            desafio.envios_ventana = envios + 1
                            desafio.save(update_fields=[
                                'codigo_hash', 'enviado_en', 'vence_en',
                                'intentos_restantes', 'inicio_ventana', 'envios_ventana',
                            ])
                            _registrar_envio(request, usuario.email)
                            aviso = 'Enviamos un nuevo código. Comprueba tu correo.'
        else:
            error = 'Acción no reconocida.'
    return render(request, 'usuarios/verificar_registro_estudiante.html',
                  _contexto(usuario, error=error, aviso=aviso))
