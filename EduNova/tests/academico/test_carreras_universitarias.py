from django.test import TestCase
from django.urls import reverse
from academico.models import Carrera, Curso, Estudiante
from usuarios.models import Usuario

class PortalUniversitarioTests(TestCase):
    def test_carreras_catalogo(self):
        self.assertTrue(Carrera.objects.filter(nombre='Ingeniería en Informática').exists())

    def test_docente_no_puede_filtrar_seccion_ajena(self):
        docente = Usuario.objects.create_user(rut='34567890-1', password='prueba123', first_name='Prueba', apellidos='Docente', rol=Usuario.Rol.DOCENTE, email='prueba@example.test')
        otra = Curso.objects.create(asignatura='Matemática', turno=True)
        self.client.force_login(docente)
        response = self.client.get(reverse('academico:home_docente'), {'seccion': otra.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['seccion_seleccionada'], '')
