"""Validaciones del nuevo selector Diurno/Vespertino del registro estudiantil."""
from django.test import TestCase
from django.urls import reverse
from academico.models import Carrera, Asignatura, CarreraAsignatura, Curso, Estudiante
from usuarios.registro_guiado import catalogos_carreras


class ModalidadRegistroTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Carrera Modalidad TEST', escuela='Informática')
        cls.asignatura = Asignatura.objects.create(codigo='MOD_TEST', nombre='Asignatura Modalidad Test')
        CarreraAsignatura.objects.create(carrera=cls.carrera, asignatura=cls.asignatura)
        cls.diurna = Curso.objects.create(asignatura_catalogo=cls.asignatura, asignatura=cls.asignatura.nombre, turno=True)
        cls.vespertina = Curso.objects.create(asignatura_catalogo=cls.asignatura, asignatura=cls.asignatura.nombre, turno=False)

    def test_catalogo_incluye_modalidad_de_cada_seccion(self):
        datos = catalogos_carreras([self.carrera])[str(self.carrera.pk)]
        secciones = {s['id']: s['modalidad'] for d in datos for s in d['secciones']}
        self.assertEqual(secciones[self.diurna.pk], 'diurno')
        self.assertEqual(secciones[self.vespertina.pk], 'vespertino')

    def test_muestra_modalidad_y_no_solicita_mencion_estudiante(self):
        respuesta = self.client.get(reverse('usuarios:registro'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="modalidad"')
        self.assertNotContains(respuesta, 'name="mencion_id"')
        self.assertContains(respuesta, 'menciones_docente')

    def test_rechaza_modalidad_invalida(self):
        respuesta = self.client.post(reverse('usuarios:registro'), {
            'rol': 'estudiante', 'carrera_id': str(self.carrera.pk),
            'anio_ingreso': '2026', 'modalidad': 'nocturno',
            'secciones': str(self.diurna.pk),
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Selecciona una modalidad válida: Diurno o Vespertino.')

    def test_rechaza_seccion_de_modalidad_distinta(self):
        respuesta = self.client.post(reverse('usuarios:registro'), {
            'rol': 'estudiante', 'carrera_id': str(self.carrera.pk),
            'anio_ingreso': '2026', 'modalidad': 'diurno',
            'secciones': str(self.vespertina.pk),
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Las secciones deben corresponder a tu carrera y modalidad seleccionadas.')
