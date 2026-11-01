"""Prueba manual de entrega ANTES de usar códigos OTP en registro."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email


class Command(BaseCommand):
    help = 'Prueba el envío a un correo de docente/director, sin OTP ni creación de cuenta.'

    def add_arguments(self, parser):
        parser.add_argument('--rol', choices=['docente', 'administrativo'], required=True)
        parser.add_argument('--destino', required=True)
        parser.add_argument('--enviar', action='store_true')

    def handle(self, *args, **options):
        correo = options['destino'].strip().lower()
        try:
            validate_email(correo)
        except ValidationError as exc:
            raise CommandError('Correo inválido.') from exc
        esperado = settings.EDUNOVA_ROLE_EMAIL_DOMAINS[options['rol']]
        if correo.rsplit('@', 1)[-1] != esperado:
            raise CommandError(f'Para este rol usa un correo @{esperado}.')
        self.stdout.write(f"Prueba {options['rol']} → {correo}")
        if not options['enviar']:
            self.stdout.write('Sin --enviar no se envía nada.')
            return
        if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
            raise CommandError('Para la prueba real, configura SMTP en .env.')
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise CommandError('Falta EMAIL_HOST_USER o EMAIL_HOST_PASSWORD.')
        mensaje = EmailMessage(
            '[EduNova] Prueba de entrega de correo académico',
            'Prueba de comunicación entre EduNova y tu correo. No es un código de verificación ni crea una cuenta.',
            settings.DEFAULT_FROM_EMAIL, [correo],
        )
        try:
            enviado = mensaje.send(fail_silently=False)
        except Exception as exc:
            raise CommandError(f'Fallo SMTP: {type(exc).__name__}. Verifica las credenciales y la conexión.') from exc
        if enviado != 1:
            raise CommandError('SMTP no confirmó el envío.')
        self.stdout.write(self.style.SUCCESS('SMTP aceptó el mensaje. Comprueba bandeja de entrada y Spam.'))
