"""Regresiones: matrícula real, código institucional y clases en calendario.

Ejecutar con PostgreSQL de pruebas separado:
python manage.py test academico.test_sincronizacion_estudiante --keepdb -v 2
"""
from datetime import time, date
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from .calendario_clases import fecha_en_periodo
from .models import (Asignatura, Carrera, CarreraAsignatura, Curso,
                     HorarioSeccion, PeriodoAcademico, Estudiante)


class SincronizacionSeccionesEstudianteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Carrera de Prueba Sincronización', escuela='Informática')
        cls.otra_carrera = Carrera.objects.create(nombre='Carrera Ajena Sincronización', escuela='Turismo')
        cls.capstone = Asignatura.objects.create(codigo='PTY4614', nombre='CAPSTONE')
        cls.ajena = Asignatura.objects.create(codigo='AJN1234', nombre='Asignatura Ajena')
        CarreraAsignatura.objects.create(carrera=cls.carrera, asignatura=cls.capstone)
        CarreraAsignatura.objects.create(carrera=cls.otra_carrera, asignatura=cls.ajena)
        cls.periodo = PeriodoAcademico.objects.create(anio=2026, semestre=2, sede='Antonio Varas')
        cls.seccion = Curso.objects.create(
            asignatura_catalogo=cls.capstone, asignatura='CAPSTONE', turno=True,
            codigo_institucional='PTY4614-005D', periodo_academico=cls.periodo,
        )
        cls.otra_seccion = Curso.objects.create(
            asignatura_catalogo=cls.capstone, asignatura='CAPSTONE', turno=True,
            codigo_institucional='PTY4614-004D', periodo_academico=cls.periodo,
        )
        cls.ajena_seccion = Curso.objects.create(
            asignatura_catalogo=cls.ajena, asignatura='Asignatura Ajena', turno=True,
            codigo_institucional='AJN1234-002D', periodo_academico=cls.periodo,
        )
        HorarioSeccion.objects.create(
            seccion=cls.seccion, dia_semana=4, hora_inicio=time(8, 31), hora_fin=time(9, 50),
        )
        cls.estudiante = Usuario.objects.create_user(
            rut='22000000-1', email='prueba@example.org', password='prueba_segura_123',
            first_name='Estudiante', apellidos='Ejemplo', rol=Usuario.Rol.ESTUDIANTE,
        )
        cls.perfil = Estudiante.objects.get(usuario=cls.estudiante)
        cls.perfil.carrera = cls.carrera
        cls.perfil.modalidad = 'diurno'
        cls.perfil.curso = cls.otra_seccion  # Simula campo heredado desincronizado.
        cls.perfil.save(update_fields=['carrera', 'modalidad', 'curso'])
        cls.perfil.secciones.add(cls.seccion)

    def setUp(self):
        self.client.force_login(self.estudiante)

    def test_calendario_usa_codigo_institucional_y_matricula_m2m(self):
        response = self.client.get(reverse('academico:home_estudiante'), {'year': 2026, 'month': 10})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('PTY4614-005D', html)
        self.assertNotIn('CAP-000-D', html)
        self.assertNotIn(self.otra_seccion.seccion, html)
        self.assertContains(response, '08:31')
        semanas = response.context['semanas']
        jueves = [d for semana in semanas for d in semana if d['numero'] == 1][0]
        viernes = [d for semana in semanas for d in semana if d['numero'] == 2][0]
        self.assertEqual(len(jueves['clases']), 1)
        self.assertEqual(jueves['clases'][0]['codigo'], 'PTY4614-005D')
        self.assertFalse(viernes['clases'])

    def test_muestra_clase_dentro_del_dia_y_hover_con_horarios(self):
        # Una clase visible en la cuadrícula y un detalle con la hora exacta.
        respuesta = self.client.get(reverse('academico:home_estudiante'), {
            'year': 2026, 'month': 10,
        })
        self.assertContains(respuesta, 'edunova-class-trigger')
        self.assertContains(respuesta, 'CAPSTONE')
        self.assertContains(respuesta, 'PTY4614-005D')
        self.assertContains(respuesta, '08:31')
        self.assertContains(respuesta, '09:50')
        self.assertContains(respuesta, 'role="tooltip"')
        jueves = next(d for w in respuesta.context['semanas'] for d in w if d['numero'] == 1)
        self.assertEqual(jueves['clases'][0]['bloques'][0]['inicio'], time(8, 31))
        self.assertEqual(jueves['clases'][0]['bloques'][0]['fin'], time(9, 50))

    def test_agrupa_bloques_de_la_misma_seccion_en_una_etiqueta(self):
        HorarioSeccion.objects.create(seccion=self.seccion, dia_semana=4,
                                     hora_inicio=time(10, 1), hora_fin=time(11, 20))
        HorarioSeccion.objects.create(seccion=self.seccion, dia_semana=4,
                                     hora_inicio=time(11, 31), hora_fin=time(12, 10))
        respuesta = self.client.get(reverse('academico:home_estudiante'), {
            'year': 2026, 'month': 10, 'seccion': str(self.seccion.pk),
        })
        jueves = next(d for w in respuesta.context['semanas'] for d in w if d['numero'] == 1)
        self.assertEqual(len(jueves['clases']), 1)
        self.assertEqual(len(jueves['clases'][0]['bloques']), 3)
        self.assertContains(respuesta, '10:01')
        self.assertContains(respuesta, '11:31')
        self.assertContains(respuesta, '12:10')

    def test_navegacion_htmx_contiene_las_clases_sin_duplicar_portal(self):
        respuesta = self.client.get(reverse('academico:home_estudiante'), {
            'year': 2026, 'month': 10, 'seccion': str(self.seccion.pk),
        }, HTTP_HX_REQUEST='true')
        html = respuesta.content.decode()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(html.count('id="calendario-mensual"'), 1)
        self.assertIn('edunova-class-trigger', html)
        self.assertIn('PTY4614-005D', html)
        self.assertNotIn('Mi espacio académico', html)
        otra_respuesta = self.client.get(reverse('academico:home_estudiante'), {
            'year': 2027, 'month': 10, 'seccion': str(self.seccion.pk),
        }, HTTP_HX_REQUEST='true')
        self.assertNotIn('edunova-class-trigger', otra_respuesta.content.decode())

    def test_filtrar_otra_seccion_no_matriculada_no_muestra_sus_clases(self):
        response = self.client.get(reverse('academico:home_estudiante'), {
            'year': 2026, 'month': 10, 'seccion': self.otra_seccion.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['seccion_seleccionada'], '')
        self.assertEqual(response.context['secciones'].count(), 1)

    def test_cambiar_seccion_actualiza_calendario_y_campo_heredado(self):
        response = self.client.post(reverse('academico:ajustar_secciones_estudiante'), {
            'secciones': [str(self.otra_seccion.pk)]
        })
        self.assertEqual(response.status_code, 302)
        self.perfil.refresh_from_db()
        self.assertEqual(set(self.perfil.secciones.values_list('pk', flat=True)), {self.otra_seccion.pk})
        self.assertEqual(self.perfil.curso_id, self.otra_seccion.pk)
        response = self.client.get(reverse('academico:home_estudiante'), {'year': 2026, 'month': 10})
        self.assertContains(response, 'PTY4614-004D')
        self.assertNotContains(response, 'PTY4614-005D')
        self.assertFalse(any(d['clases'] for week in response.context['semanas'] for d in week))

    def test_rechaza_asignatura_de_otra_carrera(self):
        response = self.client.post(reverse('academico:ajustar_secciones_estudiante'), {
            'secciones': [str(self.ajena_seccion.pk)]
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(self.perfil.secciones.values_list('pk', flat=True)), {self.seccion.pk})

    def test_rechaza_dos_secciones_de_una_asignatura(self):
        response = self.client.post(reverse('academico:ajustar_secciones_estudiante'), {
            'secciones': [str(self.seccion.pk), str(self.otra_seccion.pk)]
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(self.perfil.secciones.values_list('pk', flat=True)), {self.seccion.pk})

    def test_htmx_no_repite_el_portal(self):
        response = self.client.get(reverse('academico:home_estudiante'), {
            'year': 2026, 'month': 10
        }, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().count('id="calendario-mensual"'), 1)
        self.assertNotIn('Mi espacio académico', response.content.decode())
        self.assertContains(response, 'PTY4614-005D')

    def test_la_oferta_no_se_repite_en_otro_periodo(self):
        self.assertTrue(fecha_en_periodo(date(2026, 10, 1), self.periodo))
        self.assertFalse(fecha_en_periodo(date(2027, 10, 1), self.periodo))
        self.assertFalse(fecha_en_periodo(date(2026, 5, 1), self.periodo))
