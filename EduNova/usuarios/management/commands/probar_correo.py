"""Prueba explícita del correo SMTP: no envía nada sin --enviar."""

import smtplib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email


class Command(BaseCommand):
    help = 'Diagnostica la configuración de correo y, opcionalmente, envía un único correo de prueba.'

    def add_arguments(self, parser):
        parser.add_argument('--destino', required=True, help='Dirección que recibirá el correo de prueba.')
        parser.add_argument('--enviar', action='store_true', help='Envía realmente UN mensaje (sin esto, solo revisa configuración).')

    def handle(self, *args, **options):
        destino = options['destino'].strip()
        try:
            validate_email(destino)
        except ValidationError as exc:
            raise CommandError('El correo de destino no tiene un formato válido.') from exc

        backend = settings.EMAIL_BACKEND
        self.stdout.write(f'Backend: {backend}')
        self.stdout.write(f'Servidor: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}')
        self.stdout.write(f'TLS: {settings.EMAIL_USE_TLS}; SSL: {settings.EMAIL_USE_SSL}')
        self.stdout.write(f'Destino: {destino}')
        # Nunca imprimir contraseñas ni el contenido de .env.
        if not options['enviar']:
            self.stdout.write(self.style.WARNING('Revisión local solamente: ningún correo fue enviado.'))
            self.stdout.write('Para intentar un envío real, agrega --enviar al comando.')
            return

        if backend != 'django.core.mail.backends.smtp.EmailBackend':
            raise CommandError(
                'Para probar Gmail debes configurar EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend '
                'en .env. El backend de consola no confirma comunicación con Gmail.'
            )
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise CommandError('Configura EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en .env antes de enviar.')
        if settings.EMAIL_USE_TLS == settings.EMAIL_USE_SSL:
            raise CommandError('Usa TLS (587) o SSL (465), pero no ambos o ninguno.')
        if settings.DEFAULT_FROM_EMAIL != settings.EMAIL_HOST_USER:
            raise CommandError('Para la prueba con Gmail, DEFAULT_FROM_EMAIL debe coincidir con EMAIL_HOST_USER.')

        mensaje = EmailMessage(
            subject='[EduNova] Prueba de correo',
            body=(
                'Este es un mensaje de prueba enviado manualmente desde EduNova.\n\n'
                'Todavía no hay códigos de verificación ni eliminación de cuentas por correo.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destino],
        )
        try:
            enviados = mensaje.send(fail_silently=False)
        except smtplib.SMTPAuthenticationError as exc:
            raise CommandError(
                f'Gmail rechazó las credenciales (SMTP {exc.smtp_code}). '
                'Revisa el correo emisor y la contraseña de aplicación.'
            ) from exc
        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            raise CommandError(f'No se pudo enviar el correo ({type(exc).__name__}): {exc}') from exc

        if enviados != 1:
            raise CommandError('El servidor SMTP no confirmó la aceptación del mensaje.')
        self.stdout.write(self.style.SUCCESS('SMTP aceptó el correo de prueba. Revisa la bandeja de entrada y Spam.'))
        self.stdout.write('Esto no garantiza la entrega final: comprueba que el mensaje efectivamente llegó.')
