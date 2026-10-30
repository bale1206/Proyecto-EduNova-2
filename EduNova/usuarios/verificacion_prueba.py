"""Prueba administrativa del envío y validación de códigos OTP por correo.

Etapa 2: deliberadamente NO conecta la prueba al alta, activación o eliminación
real de cuentas. El desafío vive en la sesión de Django del superusuario.
"""

import secrets
import smtplib
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


SESSION_KEY = 'edunova_prueba_codigo_correo_v1'
TTL_SEGUNDOS = 10 * 60
ESPERA_REENVIO_SEGUNDOS = 60
MAX_INTENTOS = 5


def generar_codigo():
    """Usar un generador criptográficamente seguro, conservando ceros iniciales."""
    return f'{secrets.randbelow(1_000_000):06d}'


def _extraer_desafio(request):
    datos = request.session.get(SESSION_KEY)
    if datos and time.time() >= datos.get('vence_en', 0):
        request.session.pop(SESSION_KEY, None)
        request.session.modified = True
        return None, True
    return datos, False


def _contexto(request, *, aviso='', error='', enviado=False, verificado=False):
    datos, vencido = _extraer_desafio(request)
    if vencido and not error:
        error = 'El código venció. Solicita uno nuevo.'
    espera = 0
    if datos:
        espera = max(0, int(datos['enviado_en'] + ESPERA_REENVIO_SEGUNDOS - time.time()) + 1)
    return {
        'aviso': aviso,
        'error': error,
        'enviado': enviado,
        'verificado': verificado,
        'destino': datos['email'] if datos else '',
        'desafio_pendiente': bool(datos),
        'intentos_restantes': datos['intentos'] if datos else 0,
        'espera_reenvio': espera,
        'validez_minutos': TTL_SEGUNDOS // 60,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def probar_codigo_correo(request):
    """URL administrativa; conocer la ruta no concede permisos de envío."""
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied('Solo superusuarios pueden usar esta prueba de verificación.')

    if request.method == 'GET':
        return render(request, 'usuarios/verificacion_prueba.html', _contexto(request))

    accion = request.POST.get('accion', '')
    if accion == 'enviar':
        # No generar un segundo desafío mientras esté vigente el límite de espera.
        anterior, _ = _extraer_desafio(request)
        if anterior and time.time() < anterior['enviado_en'] + ESPERA_REENVIO_SEGUNDOS:
            return render(request, 'usuarios/verificacion_prueba.html', _contexto(
                request, error='Espera al menos 60 segundos antes de pedir otro código.'
            ))

        email = request.POST.get('email', '').strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            return render(request, 'usuarios/verificacion_prueba.html', _contexto(
                request, error='Ingresa una dirección de correo electrónico válida.'
            ))
        if len(email) > 254:
            return render(request, 'usuarios/verificacion_prueba.html', _contexto(
                request, error='El correo es demasiado largo.'
            ))

        if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
            return render(request, 'usuarios/verificacion_prueba.html', _contexto(
                request, error='Configura EMAIL_BACKEND con SMTP antes de probar el envío real.'
            ))

        codigo = generar_codigo()
        correo = EmailMessage(
            subject='[EduNova] Código de verificación de prueba',
            body=(
                'Esta es una prueba de verificación de correo de EduNova.\n\n'
                f'Tu código es: {codigo}\n\n'
                'Caduca en 10 minutos y solo se puede utilizar una vez.\n'
                'Si no solicitaste esta prueba, ignora el mensaje.\n\n'
                'Esta prueba NO crea, activa ni elimina cuentas.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        try:
            resultado = correo.send(fail_silently=False)
            if resultado != 1:
                raise RuntimeError('El servidor de correo no aceptó el mensaje.')
        except (smtplib.SMTPException, OSError, TimeoutError, RuntimeError, ValueError):
            # No exponer información sensible del proveedor SMTP en la interfaz.
            return render(request, 'usuarios/verificacion_prueba.html', _contexto(
                request, error='No se pudo enviar el correo. Revisa la configuración SMTP y la terminal del servidor.'
            ))

        ahora = time.time()
        request.session[SESSION_KEY] = {
            'email': email,
            'hash': make_password(codigo),
            'enviado_en': ahora,
            'vence_en': ahora + TTL_SEGUNDOS,
            'intentos': MAX_INTENTOS,
        }
        request.session.modified = True
        return render(request, 'usuarios/verificacion_prueba.html', _contexto(
            request, enviado=True,
            aviso='El servidor aceptó el correo. Revisa la bandeja de entrada y Spam.'
        ))

    if accion == 'verificar':
        datos, _ = _extraer_desafio(request)
        if not datos:
            return render(request, 'usuarios/verificacion_prueba.html', _contexto(
                request, error='No hay un código vigente. Solicita otro.'
            ))
        codigo = request.POST.get('codigo', '').strip()
        if not (len(codigo) == 6 and codigo.isascii() and codigo.isdecimal()):
            coincide = False
        else:
            coincide = check_password(codigo, datos['hash'])

        if coincide:
            request.session.pop(SESSION_KEY, None)  # un solo uso
            request.session.modified = True
            return render(request, 'usuarios/verificacion_prueba.html', _contexto(
                request, verificado=True,
                aviso='¡Código correcto! La prueba de comunicación y validación funcionó.'
            ))

        datos['intentos'] -= 1
        if datos['intentos'] <= 0:
            request.session.pop(SESSION_KEY, None)
            error = 'Se agotaron los intentos. Solicita un código nuevo.'
        else:
            request.session[SESSION_KEY] = datos
            error = f'Código incorrecto. Intentos restantes: {datos["intentos"]}.'
        request.session.modified = True
        return render(request, 'usuarios/verificacion_prueba.html', _contexto(request, error=error))

    return render(request, 'usuarios/verificacion_prueba.html', _contexto(
        request, error='Acción no reconocida.'
    ))
