from django.test import TestCase
from django.urls import reverse
from usuarios.forms import RegistroForm

class RegistroSimplificadoTests(TestCase):
    def test_campos_solo_basicos_y_tres_perfiles(self):
        form = RegistroForm()
        self.assertEqual(set(form.fields), {
            'rol','rut','first_name','apellidos','telefono','email','password1','password2'})
        self.assertFalse(form.fields['telefono'].required)
        self.assertTrue({'estudiante','docente','administrativo'} <=
                        {v for v, _ in form.fields['rol'].choices})

    def test_formulario_no_solicita_datos_de_catalogo(self):
        r=self.client.get(reverse('usuarios:registro'))
        self.assertEqual(r.status_code,200)
        for literal in ('name="carrera"','name="asignatura"','name="seccion"',
                        'name="modalidad"','name="mencion"'):
            self.assertNotContains(r,literal)
        self.assertContains(r,'Teléfono (opcional)')
        self.assertContains(r,'Correo electrónico')
