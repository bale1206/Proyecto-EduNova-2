"""Verifica presentación de horarios personales, sin consultar catálogos."""
from datetime import date, time
from django.test import TestCase
from django.urls import reverse
from academico.models import BloqueHorarioPersonal
from usuarios.models import Usuario

class CalendarioXLSXVisualizacionTests(TestCase):
    def setUp(self):
        self.alumno = Usuario.objects.create_user(
            '12345678-5','alumno@duocuc.cl','ClaveSegura123!',rol='estudiante',
            first_name='Alumno',apellidos='Test')
        self.docente = Usuario.objects.create_user(
            '9876543-3','docente@profesor.duoc.cl','ClaveSegura123!',rol='docente',
            first_name='Docente',apellidos='Test')
        self.director = Usuario.objects.create_user(
            '11111111-1','director@duoc.cl','ClaveSegura123!',rol='administrativo',
            first_name='Director',apellidos='Test')
        for usuario in (self.alumno,self.docente):
            BloqueHorarioPersonal.objects.create(
                usuario=usuario, asignatura='Desarrollo Web', dia_semana=1,
                hora_inicio=time(8,30), hora_fin=time(9,50),
                fecha_inicio=date(2027,3,1), fecha_fin=date(2027,3,31),
                sala='301', docente='Docente Ejemplo')

    def test_estudiante_docente_muestran_bloque_y_horas(self):
        for usuario,portal in ((self.alumno,'home_estudiante'),(self.docente,'home_docente')):
            with self.subTest(usuario=usuario.rol):
                self.client.force_login(usuario)
                ruta=reverse('academico:'+portal)
                respuesta=self.client.get(ruta,{'year':2027,'month':3})
                self.assertContains(respuesta,'Desarrollo Web')
                self.assertContains(respuesta,'08:30–09:50')
                self.assertContains(respuesta,'Sala: 301')
                self.assertContains(respuesta,'Docente Ejemplo')
                self.assertNotContains(respuesta,'name="carrera"')
                self.assertNotContains(respuesta,'name="seccion"')
                self.assertNotContains(respuesta,'name="asignatura"')
                abril=self.client.get(ruta,{'year':2027,'month':4})
                self.assertNotContains(abril,'Desarrollo Web')

    def test_director_no_recibe_horarios_de_otros(self):
        self.client.force_login(self.director)
        r=self.client.get(reverse('academico:home_administrativo'), {'year':2027,'month':3})
        self.assertEqual(r.status_code,200)
        self.assertNotContains(r,'Desarrollo Web')

    def test_navegacion_mensual_conserva_mes_sin_filtros(self):
        self.client.force_login(self.alumno)
        r=self.client.get(reverse('academico:home_estudiante'), {'year':2027,'month':3})
        self.assertContains(r,'?year=2027&month=4')
        self.assertNotContains(r,'&amp;estudiante=')
