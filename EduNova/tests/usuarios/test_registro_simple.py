from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from usuarios.models import Usuario, VerificacionCorreoEstudiante, VerificacionCorreoRol


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegistroSimpleTests(TestCase):
    def setUp(self):
        cache.clear()

    def datos(self, rol='estudiante', rut='12345678-5'):
        dominio = {'estudiante':'duocuc.cl', 'docente':'gmail.com', 'administrativo':'gmail.com'}[rol]
        return {'rol':rol, 'rut':rut, 'first_name':'Nombre', 'apellidos':'Apellido',
                'telefono':'', 'email':f'persona@{dominio}',
                'password1':'ClaveSegura123!', 'password2':'ClaveSegura123!'}

    def test_formulario_solo_datos_basicos(self):
        response = self.client.get(reverse('usuarios:registro'))
        self.assertEqual(set(response.context['form'].fields), {
            'rol', 'rut', 'first_name', 'apellidos', 'telefono', 'email', 'password1', 'password2'})
        for nombre in ('carrera_id', 'secciones', 'menciones_docente', 'anio_ingreso', 'modalidad'):
            self.assertNotContains(response, f'name="{nombre}"')

    def test_tres_roles_registran_verifican_y_entran_al_portal(self):
        for rol, rut, portal in [('estudiante','12345678-5','home_estudiante'),
                                 ('docente','11111111-1','home_docente'),
                                 ('administrativo','22222222-2','home_administrativo')]:
            with self.subTest(rol=rol):
                self.client.logout()
                modulo = 'verificacion_registro' if rol == 'estudiante' else 'verificacion_roles'
                url = 'usuarios:verificar_registro_estudiante' if rol == 'estudiante' else 'usuarios:verificar_registro_rol'
                with patch(f'usuarios.{modulo}._codigo_aleatorio', return_value='012345'):
                    response = self.client.post(reverse('usuarios:registro'), self.datos(rol, rut))
                self.assertRedirects(response, reverse(url))
                usuario = Usuario.objects.get(rut=rut)
                self.assertFalse(usuario.is_active)
                self.assertFalse(usuario.is_staff)
                self.assertFalse(usuario.is_superuser)
                self.assertEqual(len(mail.outbox[-1].to), 1)
                modelo = VerificacionCorreoEstudiante if rol == 'estudiante' else VerificacionCorreoRol
                self.assertNotEqual(modelo.objects.get(usuario=usuario).codigo_hash, '012345')
                response = self.client.post(reverse(url), {'accion':'verificar', 'codigo':'012345'}, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.redirect_chain[-1][0], reverse('academico:' + portal))
                self.assertEqual(int(self.client.session['_auth_user_id']), usuario.pk)
                usuario.refresh_from_db()
                self.assertTrue(usuario.is_active)

    def test_rechaza_dominios_ajenos_para_tres_roles(self):
        dominios_invalidos = {
            'estudiante': 'persona@gmail.com',
            'docente': 'persona@profesor.duoc.cl',
            'administrativo': 'persona@duoc.cl',
        }
        for rol, email_invalido in dominios_invalidos.items():
            with self.subTest(rol=rol):
                datos = self.datos(rol)
                datos['email'] = email_invalido
                response = self.client.post(reverse('usuarios:registro'), datos)
                self.assertEqual(response.status_code, 200)
                self.assertIn('email', response.context['form'].errors)
        self.assertFalse(Usuario.objects.exists())

    def test_no_permite_autoregistro_admin(self):
        datos = self.datos()
        datos.update(rol='administrador', is_staff='true', is_superuser='true')
        response = self.client.post(reverse('usuarios:registro'), datos)
        self.assertIn('rol', response.context['form'].errors)
        self.assertFalse(Usuario.objects.exists())

    def test_pendiente_no_puede_iniciar_sesion_y_codigo_incorrecto_no_activa(self):
        self.client.post(reverse('usuarios:registro'), self.datos('docente'))
        response = self.client.post(reverse('usuarios:login'), {'rut':'12345678-5', 'password':'ClaveSegura123!'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.post(reverse('usuarios:verificar_registro_rol'), {'accion':'verificar', 'codigo':'mal'})
        usuario = Usuario.objects.get()
        self.assertFalse(usuario.is_active)
        self.assertEqual(usuario.verificacion_correo_rol.intentos_restantes, 4)

    def test_fallo_smtp_revierte_cuenta(self):
        with patch('usuarios.verificacion_roles.EmailMessage.send', side_effect=OSError('sin red')):
            response = self.client.post(reverse('usuarios:registro'), self.datos('docente'))
        self.assertContains(response, 'No se pudo enviar el código')
        self.assertFalse(Usuario.objects.exists())

    def test_valida_rut_y_confirmacion_de_contrasena(self):
        for cambios, campo in (({'rut':'12345678-9'}, 'rut'),
                                ({'password2':'OtraClave123!'}, 'password2'),
                                ({'password1':'corta', 'password2':'corta'}, 'password2')):
            with self.subTest(campo=campo, cambios=cambios):
                response = self.client.post(reverse('usuarios:registro'), self.datos() | cambios)
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context['form'].errors)
                self.assertFalse(Usuario.objects.exists())
