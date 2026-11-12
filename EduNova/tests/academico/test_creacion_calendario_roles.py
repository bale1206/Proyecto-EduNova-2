"""Regresión del menú + Nuevo y permisos por rol.

Ejecutar únicamente contra una base PostgreSQL de PRUEBAS separada:
  python manage.py test tests.academico.test_creacion_calendario_roles --keepdb
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from academico.models import Asignatura, Carrera, CarreraAsignatura, Curso, Estudiante, Evento, TareaEstudio
from usuarios.models import Usuario


class NuevoCalendarioPorRolesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Informática pruebas menú', escuela='TI')
        cls.otra_carrera = Carrera.objects.create(nombre='Turismo pruebas menú', escuela='Turismo')
        cls.asignatura = Asignatura.objects.create(codigo='TSTNUEVO', nombre='Programación prueba')
        cls.asignatura_otra = Asignatura.objects.create(codigo='TSTOTRA', nombre='Ecoturismo prueba')
        CarreraAsignatura.objects.create(carrera=cls.carrera, asignatura=cls.asignatura)
        CarreraAsignatura.objects.create(carrera=cls.otra_carrera, asignatura=cls.asignatura_otra)
        cls.seccion = Curso.objects.create(asignatura_catalogo=cls.asignatura, turno=True)
        cls.seccion_otra = Curso.objects.create(asignatura_catalogo=cls.asignatura_otra, turno=True)
        cls.alumno = Usuario.objects.create_user(
            rut='99999999-9', username='alumno_nuevo', email='alumno@example.org',
            password='compleja-prueba-001', rol=Usuario.Rol.ESTUDIANTE,
        )
        cls.perfil = Estudiante.objects.get(usuario=cls.alumno)
        cls.perfil.carrera = cls.carrera
        cls.perfil.save(update_fields=['carrera'])
        cls.perfil.secciones.add(cls.seccion)
        cls.docente = Usuario.objects.create_user(
            rut='88888888-8', username='docente_nuevo', email='docente@example.org',
            password='compleja-prueba-002', rol=Usuario.Rol.DOCENTE,
        )
        cls.seccion.docentes.add(cls.docente)
        cls.director = Usuario.objects.create_user(
            rut='77777777-7', username='director_nuevo', email='director@example.org',
            password='compleja-prueba-003', rol=Usuario.Rol.ADMINISTRATIVO,
            carrera_dirigida=cls.carrera,
        )
        cls.director.carreras_dirigidas.add(cls.carrera)

    def test_estudiante_muestra_cuatro_opciones_y_no_formulario_bajo_calendario(self):
        self.client.force_login(self.alumno)
        respuesta = self.client.get(reverse('academico:home_estudiante'))
        self.assertEqual(respuesta.status_code, 200)
        for tipo in ('tarea', 'evaluacion', 'reunion', 'evento'):
            self.assertContains(respuesta, f'data-crear-tipo="{tipo}"')
        self.assertContains(respuesta, '+ Nuevo')

    def test_estudiante_puede_crear_evaluacion_privada(self):
        self.client.force_login(self.alumno)
        respuesta = self.client.post(reverse('academico:crear_tarea_estudiante'), {
            'tipo_actividad': 'evaluacion', 'titulo': 'Control de bases de datos',
            'seccion': str(self.seccion.pk), 'fecha_limite': '2027-06-15',
            'hora_inicio': '10:00', 'repeticion': 'ninguna', 'minutos_antes': '15',
            'prioridad': 'alta', 'color': '#4C849D',
        })
        self.assertEqual(respuesta.status_code, 302)
        personal = TareaEstudio.objects.get(estudiante=self.alumno)
        self.assertEqual(personal.tipo_actividad, 'evaluacion')
        self.assertIsNone(personal.seccion_id)
        self.assertFalse(Evento.objects.exists(), 'La evaluación personal no debe publicarse a terceros')
        self.client.force_login(self.docente)
        self.assertNotContains(self.client.get(reverse('academico:home_docente')), 'Control de bases de datos')

    def test_estudiante_no_vincula_secciones_enviadas_manualmente(self):
        self.client.force_login(self.alumno)
        respuesta = self.client.post(reverse('academico:crear_tarea_estudiante'), {
            'tipo_actividad': 'evento', 'titulo': 'Evento ajeno',
            'seccion': str(self.seccion_otra.pk), 'fecha_limite': '2027-06-15',
            'hora_inicio': '10:00', 'repeticion': 'ninguna', 'minutos_antes': '15',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertIsNone(TareaEstudio.objects.get(titulo='Evento ajeno').seccion_id)

    def test_docente_crea_solo_eventos_personales(self):
        self.client.force_login(self.docente)
        inicio = self.client.get(reverse('academico:home_docente'))
        self.assertContains(inicio, 'data-crear-tipo="evaluacion"')
        self.assertNotContains(inicio, 'data-crear-tipo="tarea"')
        base = {'titulo': 'Evaluación del docente', 'tipo': 'evaluacion',
                'fecha': '2027-06-15', 'hora_inicio': '10:00', 'seccion': str(self.seccion.pk)}
        self.assertEqual(self.client.post(reverse('academico:crear_evento'), base).status_code, 302)
        self.assertTrue(Evento.objects.filter(titulo='Evaluación del docente', creado_por=self.docente, curso__isnull=True).exists())
        base['seccion'] = str(self.seccion_otra.pk)
        self.assertEqual(self.client.post(reverse('academico:crear_evento'), base).status_code, 302)
        self.assertFalse(Evento.objects.filter(creado_por=self.docente, curso__isnull=False).exists())

    def test_director_sin_vinculos_de_carrera_y_tipos_permitidos(self):
        self.client.force_login(self.director)
        inicio = self.client.get(reverse('academico:home_administrativo'))
        self.assertContains(inicio, 'data-crear-tipo="reunion"')
        self.assertContains(inicio, 'data-crear-tipo="otro"')
        self.assertNotContains(inicio, 'data-crear-tipo="evaluacion"')
        base = {'titulo': 'Reunión de carrera', 'tipo': 'reunion',
                'alcance': 'carrera', 'fecha': '2027-06-15',
                'carrera': str(self.carrera.pk)}
        self.assertEqual(self.client.post(reverse('academico:crear_evento'), base).status_code, 302)
        self.assertTrue(Evento.objects.filter(carrera__isnull=True, creado_por=self.director, titulo='Reunión de carrera').exists())
        base['carrera'] = str(self.otra_carrera.pk)
        self.assertEqual(self.client.post(reverse('academico:crear_evento'), base).status_code, 302)
        self.assertFalse(Evento.objects.filter(creado_por=self.director, carrera__isnull=False).exists())
        base['carrera'] = str(self.carrera.pk)
        base['tipo'] = 'evaluacion'
        self.assertEqual(self.client.post(reverse('academico:crear_evento'), base).status_code, 403)
