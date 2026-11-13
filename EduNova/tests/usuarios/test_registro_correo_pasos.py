from django.test import TestCase
from django.urls import reverse
from usuarios.forms import RegistroForm

class ValidacionCorreoPasoTests(TestCase):
    def test_recupera_interfaz_por_pasos_para_tres_roles(self):
        r=self.client.get(reverse('usuarios:registro'))
        self.assertEqual(r.status_code,200)
        for literal in ('Paso 1 de 3','data-role="estudiante"','data-role="docente"',
                        'data-role="administrativo"','id="paso-continuar"',
                        'registro-validacion.js','registro-guiado-simple.js'):
            self.assertContains(r,literal)
        self.assertNotContains(r,'name="carrera"')
        self.assertNotContains(r,'name="asignatura"')
        self.assertNotContains(r,'name="seccion"')

    def test_el_servidor_rechaza_correo_incorrecto_en_tres_roles(self):
        for role, email in (('estudiante','persona@gmail.com'),('docente','doc@duocuc.cl'),
                            ('administrativo','director@duoc.cl')):
            with self.subTest(rol=role):
                f=RegistroForm(data={
                    'rol':role,'rut':'12345678-5','first_name':'Prueba',
                    'apellidos':'Test','telefono':'','email':email,
                    'password1':'ClaveSegura123!', 'password2':'ClaveSegura123!'})
                self.assertFalse(f.is_valid())
                self.assertIn('email',f.errors)

    def test_gmail_para_docente_y_director_y_dominio_institucional_para_estudiante(self):
        from django.conf import settings
        self.assertEqual(settings.EDUNOVA_ROLE_EMAIL_DOMAINS['docente'], 'gmail.com')
        self.assertEqual(settings.EDUNOVA_ROLE_EMAIL_DOMAINS['administrativo'], 'gmail.com')
        for rol, correo in (('docente', 'profesor@gmail.com'),
                            ('administrativo', 'director@gmail.com'),
                            ('estudiante', 'alumno@duocuc.cl')):
            with self.subTest(rol=rol):
                formulario = RegistroForm(data={
                    'rol': rol, 'rut': '12345678-5', 'first_name': 'Prueba',
                    'apellidos': 'Test', 'telefono': '', 'email': correo,
                    'password1': 'ClaveSegura123!', 'password2': 'ClaveSegura123!',
                })
                self.assertTrue(formulario.is_valid(), formulario.errors.as_text())

    def test_rechaza_gmail_para_estudiante_y_sufijos_falsos(self):
        for rol, correo in (('estudiante','estudiante@gmail.com'),
                            ('docente','docente@gmail.com.otra.cl'),
                            ('administrativo','director@duoc.cl')):
            with self.subTest(rol=rol):
                formulario = RegistroForm(data={
                    'rol': rol, 'rut': '12345678-5', 'first_name': 'Prueba',
                    'apellidos': 'Test', 'telefono': '', 'email': correo,
                    'password1': 'ClaveSegura123!', 'password2': 'ClaveSegura123!',
                })
                self.assertFalse(formulario.is_valid())
                self.assertIn('email', formulario.errors)
