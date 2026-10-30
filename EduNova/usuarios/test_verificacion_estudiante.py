"""Pruebas de registro estudiantil con correo (sin SMTP real)."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academico.models import Asignatura, Carrera, CarreraAsignatura, Curso, Estudiante
from .forms import RegistroForm
from .models import VerificacionCorreoEstudiante
from .verificacion_registro import SESSION_KEY


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='no-reply@edunova.test')
class VerificacionEstudianteTests(TestCase):
    def setUp(self):
        # Los límites por IP/correo se comparten mediante cache en cada test.
        cache.clear()

    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Informática prueba OTP', escuela='Informática')
        cls.asignatura = Asignatura.objects.create(codigo='OTP101', nombre='Asignatura prueba OTP')
        CarreraAsignatura.objects.create(carrera=cls.carrera, asignatura=cls.asignatura)
        cls.seccion = Curso.objects.create(asignatura_catalogo=cls.asignatura, turno=True)

    def datos(self, **extra):
        datos = {
            'rol': 'estudiante', 'carrera_id': str(self.carrera.pk),
            'modalidad': 'diurno', 'anio_ingreso': str(timezone.localdate().year),
            'secciones': [str(self.seccion.pk)],
            'rut': '11111111-1', 'first_name': 'Andrea', 'apellidos': 'Estudiante',
            'email': 'andrea@duocuc.cl', 'telefono': '',
            'password1': 'ClaveSuperSegura!2026', 'password2': 'ClaveSuperSegura!2026',
        }
        datos.update(extra)
        return datos

    def test_estudiante_solo_admite_correo_institucional(self):
        form = RegistroForm(self.datos(email='andrea@gmail.com'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertFalse(get_user_model().objects.filter(rut='11111111-1').exists())

    @patch('usuarios.verificacion_registro._codigo_aleatorio', return_value='000042')
    def test_crea_cuenta_inactiva_y_envia_codigo(self, _codigo):
        respuesta = self.client.post(reverse('usuarios:registro'), self.datos())
        self.assertRedirects(respuesta, reverse('usuarios:verificar_registro_estudiante'))
        usuario = get_user_model().objects.get(rut='11111111-1')
        self.assertFalse(usuario.is_active)
        self.assertEqual(Estudiante.objects.get(usuario=usuario).carrera, self.carrera)
        self.assertTrue(Estudiante.objects.get(usuario=usuario).secciones.filter(pk=self.seccion.pk).exists())
        self.assertEqual(self.client.session[SESSION_KEY], usuario.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('000042', mail.outbox[0].body)
        self.assertNotEqual(usuario.verificacion_correo_estudiante.codigo_hash, '000042')
        self.assertIsNone(self.client.session.get('_auth_user_id'))
        self.assertIsNone(self.client.post(reverse('usuarios:login'), {
            'rut': usuario.rut, 'password': 'ClaveSuperSegura!2026',
        }).wsgi_request.user.pk)

    @patch('usuarios.verificacion_registro._codigo_aleatorio', return_value='000042')
    def test_codigo_correcto_activa_una_sola_vez(self, _codigo):
        self.client.post(reverse('usuarios:registro'), self.datos())
        url = reverse('usuarios:verificar_registro_estudiante')
        respuesta = self.client.post(url, {'accion': 'verificar', 'codigo': '000042'})
        self.assertRedirects(respuesta, reverse('usuarios:post_login_redirect'), fetch_redirect_response=False)
        usuario = get_user_model().objects.get(rut='11111111-1')
        self.assertTrue(usuario.is_active)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertIsNotNone(usuario.verificacion_correo_estudiante.confirmado_en)
        self.assertEqual(usuario.verificacion_correo_estudiante.codigo_hash, '')

    @patch('usuarios.verificacion_registro._codigo_aleatorio', return_value='000042')
    def test_cinco_errores_no_activan_cuenta(self, _codigo):
        self.client.post(reverse('usuarios:registro'), self.datos())
        url = reverse('usuarios:verificar_registro_estudiante')
        for _ in range(5):
            self.client.post(url, {'accion': 'verificar', 'codigo': '999999'})
        desafio = VerificacionCorreoEstudiante.objects.get()
        self.assertEqual(desafio.intentos_restantes, 0)
        respuesta = self.client.post(url, {'accion': 'verificar', 'codigo': '000042'})
        self.assertContains(respuesta, 'Se agotaron los intentos')
        self.assertFalse(get_user_model().objects.get(rut='11111111-1').is_active)

    @patch('usuarios.verificacion_registro._codigo_aleatorio', return_value='000042')
    def test_codigo_caducado_no_activa_cuenta(self, _codigo):
        self.client.post(reverse('usuarios:registro'), self.datos())
        VerificacionCorreoEstudiante.objects.update(vence_en=timezone.now() - timedelta(minutes=1))
        respuesta = self.client.post(reverse('usuarios:verificar_registro_estudiante'),
                                    {'accion': 'verificar', 'codigo': '000042'})
        self.assertContains(respuesta, 'venció')
        self.assertFalse(get_user_model().objects.get(rut='11111111-1').is_active)

    @patch('usuarios.verificacion_registro._codigo_aleatorio', return_value='000042')
    def test_reenvio_exige_espera_y_reemplaza_codigo(self, _codigo):
        self.client.post(reverse('usuarios:registro'), self.datos())
        url = reverse('usuarios:verificar_registro_estudiante')
        r = self.client.post(url, {'accion': 'reenviar'})
        self.assertContains(r, 'Espera 60 segundos')
        self.assertEqual(len(mail.outbox), 1)
        VerificacionCorreoEstudiante.objects.update(enviado_en=timezone.now() - timedelta(seconds=65))
        with patch('usuarios.verificacion_registro._codigo_aleatorio', return_value='000043'):
            r = self.client.post(url, {'accion': 'reenviar'})
        self.assertContains(r, 'Enviamos un nuevo código')
        self.assertEqual(len(mail.outbox), 2)
        self.assertContains(self.client.post(url, {'accion': 'verificar', 'codigo': '000042'}),
                            'Código incorrecto')

    @patch('usuarios.verificacion_registro._codigo_aleatorio', return_value='000042')
    def test_smtp_fallido_no_deja_cuenta_inactiva_huerfana(self, _codigo):
        with patch('usuarios.verificacion_registro.EmailMessage.send', side_effect=OSError('smtp')):
            respuesta = self.client.post(reverse('usuarios:registro'), self.datos())
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(rut='11111111-1').exists())
        self.assertFalse(VerificacionCorreoEstudiante.objects.exists())

    def test_ruta_sin_registro_pendiente_redirige(self):
        self.assertRedirects(self.client.get(reverse('usuarios:verificar_registro_estudiante')),
                             reverse('usuarios:registro'))
