"""Regresiones de menciones por carrera y filtrado del registro universitario.

Ejecutar después de las migraciones: python manage.py test academico.test_menciones_registro
"""
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from academico.models import Asignatura, Carrera, CarreraAsignatura, Estudiante, MencionCarrera
from usuarios.registro_guiado import catalogos_carreras


class MencionesCarreraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Carrera de prueba con menciones', escuela='Informática')
        cls.otra_carrera = Carrera.objects.create(nombre='Carrera distinta de prueba', escuela='Informática')
        cls.ia = MencionCarrera.objects.create(carrera=cls.carrera, nombre='Inteligencia Artificial')
        cls.redes = MencionCarrera.objects.create(carrera=cls.carrera, nombre='Redes')
        cls.otra_mencion = MencionCarrera.objects.create(carrera=cls.otra_carrera, nombre='Gestión')
        cls.base = Asignatura.objects.create(codigo='TEST_BASE', nombre='Base común')
        cls.especial = Asignatura.objects.create(codigo='TEST_IA', nombre='Mención IA')
        cls.plan_comun = CarreraAsignatura.objects.create(carrera=cls.carrera, asignatura=cls.base)
        cls.plan_ia = CarreraAsignatura.objects.create(carrera=cls.carrera, asignatura=cls.especial,
                                                       mencion=cls.ia, anio_plan=3, semestre_plan=2)

    def test_catalogo_distingue_menciones_y_comunes(self):
        catalogo = catalogos_carreras([self.carrera])[str(self.carrera.pk)]
        asignaturas = {p['codigo']: p for p in catalogo}
        self.assertIsNone(asignaturas['TEST_BASE']['mencion'])
        self.assertEqual(asignaturas['TEST_IA']['mencion'], self.ia.pk)

    def test_no_permitir_mencion_ajena_en_plan(self):
        plan = CarreraAsignatura(carrera=self.carrera, asignatura=self.especial,
                                mencion=self.otra_mencion)
        with self.assertRaises(ValidationError):
            plan.clean()

    def test_no_permitir_mencion_ajena_en_estudiante(self):
        perfil = Estudiante(carrera=self.carrera, mencion=self.otra_mencion)
        with self.assertRaises(ValidationError):
            perfil.clean()

    def test_permite_variantes_de_una_asignatura_en_distintas_menciones(self):
        CarreraAsignatura.objects.create(carrera=self.carrera, asignatura=self.especial, mencion=self.redes)
        self.assertEqual(CarreraAsignatura.objects.filter(carrera=self.carrera,
                         asignatura=self.especial).count(), 2)

    def test_registro_estudiante_no_acepta_mencion_enviada_manualmente(self):
        respuesta = self.client.post(reverse('usuarios:registro'), {
            'rol': 'estudiante', 'carrera_id': str(self.carrera.pk),
            'mencion_id': str(self.otra_mencion.pk), 'modalidad': 'diurno', 'anio_ingreso': '2026',
            'secciones': '99999999',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'La mención ya no se selecciona durante el registro estudiantil.')

    def test_registro_docente_rechaza_mencion_de_carrera_no_seleccionada(self):
        respuesta = self.client.post(reverse('usuarios:registro'), {
            'rol': 'docente', 'carreras': str(self.carrera.pk),
            'menciones_docente': str(self.otra_mencion.pk),
            'asignaturas': str(self.base.pk), 'secciones': '99999999',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Las menciones deben pertenecer a las carreras seleccionadas.')
