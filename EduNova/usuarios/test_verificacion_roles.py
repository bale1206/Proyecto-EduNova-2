"""Integración de pruebas OTP de docentes y directores, sin correo real."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academico.models import Asignatura, Carrera, CarreraAsignatura, Curso
from .models import VerificacionCorreoRol
from .verificacion_roles import SESSION_KEY_ROLES


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='prueba@edunova.test', EDUNOVA_ROLE_OTP_READY=True)
class VerificacionPersonalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Carrera OTP personal', escuela='Tecnología')
        cls.asignatura = Asignatura.objects.create(codigo='DOCOTP', nombre='Docencia OTP')
        CarreraAsignatura.objects.create(carrera=cls.carrera, asignatura=cls.asignatura)
        cls.seccion = Curso.objects.create(asignatura_catalogo=cls.asignatura, turno=True)

    def setUp(self):
        cache.clear()

    def _datos(self, rol):
        from django.conf import settings
        correo = f'validacion@{settings.EDUNOVA_ROLE_EMAIL_DOMAINS[rol]}'
        datos = {
            'rol': rol, 'rut': '12456789-6', 'first_name': 'Prueba', 'apellidos': 'Personal',
            'email': correo, 'telefono': '', 'password1': 'ClaveCompleja_2026!',
            'password2': 'ClaveCompleja_2026!', 'carreras': [str(self.carrera.pk)],
        }
        if rol == 'docente':
            datos.update(asignaturas=[str(self.asignatura.pk)], secciones=[str(self.seccion.pk)])
        else:
            datos['escuela'] = self.carrera.escuela
        return datos

    @patch('usuarios.verificacion_roles._codigo_aleatorio', return_value='000042')
    def test_docente_codigo_correcto_activa_cuenta(self, _codigo):
        respuesta = self.client.post(reverse('usuarios:registro'), self._datos('docente'))
        self.assertRedirects(respuesta, reverse('usuarios:verificar_registro_rol'))
        usuario = get_user_model().objects.get(rut='12456789-6')
        self.assertFalse(usuario.is_active)
        self.assertEqual(self.client.session[SESSION_KEY_ROLES], usuario.pk)
        self.assertIn('000042', mail.outbox[0].body)
        self.assertNotEqual(usuario.verificacion_correo_rol.codigo_hash, '000042')
        verificar = self.client.post(reverse('usuarios:verificar_registro_rol'),
                                    {'accion': 'verificar', 'codigo': '000042'})
        self.assertRedirects(verificar, reverse('usuarios:login'))
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)  # se activa tras confirmar el código
        self.assertIsNotNone(usuario.verificacion_correo_rol.confirmado_en)
        acceso = self.client.post(reverse('usuarios:login'),
                                  {'rut': usuario.rut, 'password': 'ClaveCompleja_2026!'})
        self.assertRedirects(acceso, reverse('usuarios:post_login_redirect'),
                             fetch_redirect_response=False)

    @patch('usuarios.verificacion_roles._codigo_aleatorio', return_value='000042')
    def test_director_verificado_activa_cuenta(self, _codigo):
        respuesta = self.client.post(reverse('usuarios:registro'), self._datos('administrativo'))
        self.assertRedirects(respuesta, reverse('usuarios:verificar_registro_rol'))
        usuario = get_user_model().objects.get(rut='12456789-6')
        self.assertFalse(usuario.is_active)
        self.client.post(reverse('usuarios:verificar_registro_rol'),
                         {'accion': 'verificar', 'codigo': '000042'})
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertIsNotNone(usuario.verificacion_correo_rol.confirmado_en)

    def test_rechaza_otro_dominio_en_ambos_roles(self):
        from django.conf import settings
        from .forms import RegistroForm
        for rol in ('docente', 'administrativo'):
            with self.subTest(rol=rol):
                inesperado = ('duoc.cl' if settings.EDUNOVA_ROLE_EMAIL_DOMAINS[rol] == 'gmail.com'
                              else 'gmail.com')
                form = RegistroForm(self._datos(rol) | {'email': f'persona@{inesperado}'})
                self.assertFalse(form.is_valid())
                self.assertIn('email', form.errors)

    @patch('usuarios.verificacion_roles._codigo_aleatorio', return_value='000042')
    def test_bloqueo_por_intentos_y_caducidad(self, _codigo):
        self.client.post(reverse('usuarios:registro'), self._datos('docente'))
        url = reverse('usuarios:verificar_registro_rol')
        for _ in range(5):
            self.client.post(url, {'accion': 'verificar', 'codigo': '111111'})
        usuario = get_user_model().objects.get(rut='12456789-6')
        self.assertEqual(usuario.verificacion_correo_rol.intentos_restantes, 0)
        self.client.post(url, {'accion': 'verificar', 'codigo': '000042'})
        usuario.verificacion_correo_rol.refresh_from_db()
        self.assertIsNone(usuario.verificacion_correo_rol.confirmado_en)
        VerificacionCorreoRol.objects.filter(usuario=usuario).update(
            intentos_restantes=5, vence_en=timezone.now() - timedelta(seconds=1))
        self.client.post(url, {'accion': 'verificar', 'codigo': '000042'})
        usuario.verificacion_correo_rol.refresh_from_db()
        self.assertIsNone(usuario.verificacion_correo_rol.confirmado_en)

    @patch('usuarios.verificacion_roles._codigo_aleatorio', return_value='000042')
    def test_error_smtp_revierte_registro(self, _codigo):
        with patch('usuarios.verificacion_roles._enviar_email', side_effect=OSError('smtp caído')):
            # Normalmente _enviar_email traduce excepciones de red a ErrorCorreoRol;
            # simulamos ese tipo esperado para probar el rollback de la transacción.
            from .verificacion_roles import ErrorCorreoRol
            with patch('usuarios.verificacion_roles._enviar_email', side_effect=ErrorCorreoRol('SMTP falló')):
                respuesta = self.client.post(reverse('usuarios:registro'), self._datos('docente'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(rut='12456789-6').exists())
