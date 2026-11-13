"""Regresión del punto 2: calendarios personales de los tres perfiles.

Verifica que carreras, asignaturas y secciones del catálogo histórico no
sean requisitos ni filtros de los calendarios activos. No borra datos reales.
"""
from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from academico.models import (
    Asignatura, BloqueHorarioPersonal, Carrera, CarreraAsignatura, Evento,
)
from usuarios.models import Usuario


class CalendariosIndependientesDelCatalogoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = Usuario.objects.create_user(
            '12345678-5', 'estudiante@duocuc.cl', 'ClaveSegura123!',
            rol=Usuario.Rol.ESTUDIANTE, first_name='Estudiante', apellidos='Prueba',
        )
        cls.docente = Usuario.objects.create_user(
            '9876543-3', 'docente@profesor.duoc.cl', 'ClaveSegura123!',
            rol=Usuario.Rol.DOCENTE, first_name='Docente', apellidos='Prueba',
        )
        cls.director = Usuario.objects.create_user(
            '11111111-1', 'director@duoc.cl', 'ClaveSegura123!',
            rol=Usuario.Rol.ADMINISTRATIVO, first_name='Director', apellidos='Prueba',
        )
        cls.carrera_antigua = Carrera.objects.create(
            nombre='Carrera histórica de pruebas', escuela='Escuela de pruebas')
        cls.asignatura_antigua = Asignatura.objects.create(
            codigo='HIST2027', nombre='Asignatura histórica del catálogo')
        CarreraAsignatura.objects.create(
            carrera=cls.carrera_antigua, asignatura=cls.asignatura_antigua)
        for usuario, asignatura in (
            (cls.estudiante, 'Horario personal estudiante'),
            (cls.docente, 'Horario personal docente'),
        ):
            BloqueHorarioPersonal.objects.create(
                usuario=usuario, asignatura=asignatura, dia_semana=1,
                hora_inicio=time(8, 30), hora_fin=time(9, 50),
                fecha_inicio=date(2027, 3, 1), fecha_fin=date(2027, 3, 31),
                sala='Sala de pruebas', docente='',
            )

    def perfiles(self):
        return (
            (self.estudiante, 'home_estudiante'),
            (self.docente, 'home_docente'),
            (self.director, 'home_administrativo'),
        )

    def test_los_tres_calendarios_no_muestran_selectores_academicos(self):
        selectores_obsoletos = (
            'name="carrera"', 'name="asignatura"', 'name="seccion"',
            'id="seccion-docente"', 'id="filtro-carrera"',
            'id="filtro-seccion"', 'id="import-carrera"',
            '&estudiante=',
        )
        for usuario, portal in self.perfiles():
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                pagina = self.client.get(reverse('academico:' + portal), {
                    'year': '2027', 'month': '3',
                })
                self.assertEqual(pagina.status_code, 200)
                self.assertContains(pagina, 'calendario-mensual')
                for selector in selectores_obsoletos:
                    self.assertNotContains(pagina, selector)
                self.assertNotContains(pagina, 'Asignatura histórica del catálogo')

    def test_clases_solo_desde_horario_personal_del_usuario(self):
        for usuario, portal in self.perfiles():
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                pagina = self.client.get(reverse('academico:' + portal), {
                    'year': '2027', 'month': '3', 'carrera': '99999',
                    'asignatura': '99999', 'seccion': '99999',
                })
                self.assertEqual(pagina.status_code, 200)
                esperado = {
                    Usuario.Rol.ESTUDIANTE: 'Horario personal estudiante',
                    Usuario.Rol.DOCENTE: 'Horario personal docente',
                    Usuario.Rol.ADMINISTRATIVO: None,
                }[usuario.rol]
                for nombre in ('Horario personal estudiante', 'Horario personal docente'):
                    if nombre == esperado:
                        self.assertContains(pagina, nombre)
                    else:
                        self.assertNotContains(pagina, nombre)
                self.assertNotContains(pagina, 'Asignatura histórica del catálogo')

    def test_navegacion_mensual_compartida_sin_parametros_de_matricula(self):
        for usuario, portal in self.perfiles():
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                pagina = self.client.get(reverse('academico:' + portal), {
                    'year': '2027', 'month': '3',
                }, HTTP_HX_REQUEST='true')
                self.assertEqual(pagina.status_code, 200)
                self.assertContains(pagina, 'hx-get="?year=2027&month=2"')
                self.assertContains(pagina, 'hx-get="?year=2027&month=4"')
                self.assertNotContains(pagina, '&amp;estudiante=')
                self.assertNotContains(pagina, 'name="carrera"')
                self.assertNotContains(pagina, 'name="seccion"')

    def test_antigua_pagina_estudiantil_de_secciones_no_se_utiliza(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('academico:ajustar_secciones_estudiante'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('academico:importar_horario'))

    def test_eventos_de_docente_y_director_no_vinculan_carrera_ni_seccion(self):
        for usuario, portal in self.perfiles()[1:]:
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                respuesta = self.client.post(reverse('academico:crear_evento'), {
                    'titulo': 'Evento personal independiente',
                    'tipo': 'reunion', 'fecha': '2027-03-08',
                    'hora_inicio': '10:00', 'hora_fin': '11:00',
                    'carrera': str(self.carrera_antigua.pk),
                    'seccion': '99999', 'asignatura': str(self.asignatura_antigua.pk),
                })
                self.assertEqual(respuesta.status_code, 302)
                evento = Evento.objects.get(creado_por=usuario)
                self.assertIsNone(evento.carrera_id)
                self.assertIsNone(evento.curso_id)

    def test_los_datos_historicos_permanecen_intactos(self):
        for usuario, portal in self.perfiles():
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse('academico:' + portal)).status_code, 200)
        self.assertTrue(Carrera.objects.filter(pk=self.carrera_antigua.pk).exists())
        self.assertTrue(Asignatura.objects.filter(pk=self.asignatura_antigua.pk).exists())
        self.assertTrue(CarreraAsignatura.objects.filter(
            carrera=self.carrera_antigua, asignatura=self.asignatura_antigua).exists())
