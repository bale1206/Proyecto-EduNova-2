"""Pruebas de etapa 1; no abren conexión externa ni usan Supabase."""

from unittest.mock import patch
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class PruebaCorreoCommandTests(SimpleTestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_sin_bandera_enviar_no_envia(self):
        salida = StringIO()
        with patch('usuarios.management.commands.probar_correo.EmailMessage') as mensaje:
            call_command('probar_correo', destino='ejemplo@gmail.com', stdout=salida)
            mensaje.assert_not_called()
        self.assertIn('ningún correo fue enviado', salida.getvalue())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_no_finge_envio_con_backend_consola(self):
        with self.assertRaises(CommandError):
            call_command('probar_correo', destino='ejemplo@gmail.com', enviar=True)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST_USER='emisor@gmail.com',
        EMAIL_HOST_PASSWORD='solo-prueba-local',
        DEFAULT_FROM_EMAIL='emisor@gmail.com',
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
    )
    def test_envio_con_smtp_simulado(self):
        with patch('usuarios.management.commands.probar_correo.EmailMessage') as mensaje:
            mensaje.return_value.send.return_value = 1
            call_command('probar_correo', destino='destino@gmail.com', enviar=True, stdout=StringIO())
            self.assertEqual(mensaje.call_count, 1)
            mensaje.return_value.send.assert_called_once_with(fail_silently=False)
