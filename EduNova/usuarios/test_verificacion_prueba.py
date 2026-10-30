"""Pruebas aisladas del flujo OTP de demostración; no envían correo real."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .verificacion_prueba import SESSION_KEY


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
    DEFAULT_FROM_EMAIL='pruebas@gmail.com',
)
class PruebaOTPTests(TestCase):
    def setUp(self):
        self.url = reverse('usuarios:verificacion_prueba')
        self.admin = get_user_model().objects.create_superuser(
            rut='11111111-1', email='admin@gmail.com', password='SoloEnTests!123',
            first_name='Admin', apellidos='Demo',
        )
        self.client.force_login(self.admin)

    def enviar(self, destino='destino@gmail.com'):
        with patch('usuarios.verificacion_prueba.generar_codigo', return_value='000042'):
            with patch('usuarios.verificacion_prueba.EmailMessage') as mensaje:
                mensaje.return_value.send.return_value = 1
                respuesta = self.client.post(self.url, {'accion': 'enviar', 'email': destino})
                return respuesta, mensaje

    def test_solo_superusuario_puede_abrir_pagina(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        usuario = get_user_model().objects.create_user(
            rut='22222222-2', email='otro@gmail.com', password='Prueba!123',
            rol='docente', first_name='Doc', apellidos='Test',
        )
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'accion':'enviar','email':'destino@gmail.com'}).status_code, 403)

    def test_envia_codigo_y_guarda_solo_hash(self):
        respuesta, correo = self.enviar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['desafio_pendiente'])
        self.assertEqual(correo.call_count, 1)
        sesion = self.client.session[SESSION_KEY]
        self.assertNotEqual(sesion['hash'], '000042')
        self.assertTrue(sesion['hash'].startswith('pbkdf2_') or '$' in sesion['hash'])
        self.assertEqual(sesion['intentos'], 5)
        self.assertIn('000042', correo.call_args.kwargs['body'])

    def test_codigo_correcto_se_usa_una_sola_vez(self):
        self.enviar()
        respuesta = self.client.post(self.url, {'accion':'verificar', 'codigo':'000042'})
        self.assertTrue(respuesta.context['verificado'])
        self.assertNotIn(SESSION_KEY, self.client.session)
        segundo = self.client.post(self.url, {'accion':'verificar', 'codigo':'000042'})
        self.assertFalse(segundo.context['verificado'])

    def test_cinco_errores_invalidan_codigo(self):
        self.enviar()
        for _ in range(5):
            self.client.post(self.url, {'accion':'verificar', 'codigo':'123456'})
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_codigo_vencido_es_rechazado(self):
        self.enviar()
        sesion = self.client.session
        datos = sesion[SESSION_KEY]
        datos['vence_en'] = 0
        sesion[SESSION_KEY] = datos
        sesion.save()
        respuesta = self.client.post(self.url, {'accion':'verificar', 'codigo':'000042'})
        self.assertFalse(respuesta.context['verificado'])
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_no_permita_reenviar_antes_de_60_segundos(self):
        self.enviar()
        respuesta, correo = self.enviar()
        correo.assert_not_called()
        self.assertContains(respuesta, 'Espera al menos 60 segundos')

    def test_correo_invalido_no_envia(self):
        respuesta, correo = self.enviar(destino='direccion inválida')
        correo.assert_not_called()
        self.assertFalse(respuesta.context['desafio_pendiente'])

    def test_fallo_smtp_no_crea_codigo(self):
        with patch('usuarios.verificacion_prueba.EmailMessage') as correo:
            correo.return_value.send.side_effect = OSError('red no disponible')
            respuesta = self.client.post(self.url, {'accion':'enviar', 'email':'destino@gmail.com'})
        self.assertFalse(respuesta.context['desafio_pendiente'])
        self.assertNotIn(SESSION_KEY, self.client.session)
