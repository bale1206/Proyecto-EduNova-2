"""Pruebas de las dos planillas vigentes de EduNova."""
from django.test import TestCase
from django.urls import reverse
from academico.models import Carrera, Estudiante, Asignatura, CarreraAsignatura
from usuarios.models import Usuario
from io import BytesIO


class PlanillasTests(TestCase):
    def setUp(self):
        self.carrera = Carrera.objects.create(nombre='Carrera Pruebas CSV', escuela='Pruebas')
        self.director = Usuario.objects.create_user(rut='11111111-1', password='clave-prueba-2026',
            rol='administrativo', carrera_dirigida=self.carrera, email='director@example.test')
        self.client.force_login(self.director)

    def test_solamente_dos_planillas(self):
        r = self.client.get(reverse('academico:panel_csv'))
        self.assertContains(r, 'Docentes y asignaturas')
        self.assertContains(r, 'Estudiantes y situación académica')
        self.assertEqual(self.client.get(reverse('academico:exportar_csv', args=['academico_curso'])).status_code, 403)
        self.assertEqual(self.client.get(reverse('academico:exportar_csv', args=['docentes'])).status_code, 200)

    def test_actualizar_progreso_estatico(self):
        est = Estudiante.objects.create(rut_estudiante='22222222-2', nombre_completo='Caso Prueba', carrera=self.carrera)
        payload = 'rut,carrera,anio_carrera,estado_avance\n22222222-2,Carrera Pruebas CSV,2,con_retraso\n'.encode()
        f = BytesIO(payload);f.name = 'estudiantes.csv';f.size=len(payload)
        self.client.post(reverse('academico:importar_csv', args=['estudiantes']), {'archivo': f})
        est.refresh_from_db()
        self.assertEqual(est.anio_carrera, 2)
        self.assertEqual(est.estado_avance, 'con_retraso')

    def test_docente_asignaturas_por_codigo(self):
        docente = Usuario.objects.create_user(rut='33333333-3', password='clave-prueba-2026', rol='docente', email='doc@example.test')
        subject=Asignatura.objects.create(codigo='SUB-101', nombre='Asignatura Prueba')
        CarreraAsignatura.objects.create(carrera=self.carrera, asignatura=subject)
        payload = b'rut,codigos_asignaturas\n33333333-3,SUB-101\n'
        f=BytesIO(payload);f.name='docentes.csv';f.size=len(payload)
        self.client.post(reverse('academico:importar_csv', args=['docentes']), {'archivo':f})
        self.assertTrue(docente.asignaturas_asociadas.filter(pk=subject.pk).exists())
