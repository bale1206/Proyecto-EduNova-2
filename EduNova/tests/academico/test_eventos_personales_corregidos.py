"""Pruebas del calendario personal, sin conexión a datos productivos.

python manage.py test tests.academico.test_eventos_personales_corregidos --settings=edunova_project.settings_test
"""
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from academico.models import Evento, TareaEstudio
from usuarios.models import Usuario


class CreacionPersonalCorregidaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = Usuario.objects.create_user(
            '12345678-5', 'alumno@duocuc.cl', 'ClaveSegura123!',
            rol='estudiante', first_name='Alumno', apellidos='Prueba')
        cls.docente = Usuario.objects.create_user(
            '9876543-3', 'docente@gmail.com', 'ClaveSegura123!',
            rol='docente', first_name='Docente', apellidos='Prueba')
        cls.director = Usuario.objects.create_user(
            '11111111-1', 'director@gmail.com', 'ClaveSegura123!',
            rol='administrativo', first_name='Director', apellidos='Prueba')

    def test_crear_reuniones_y_eventos_sin_seccion_para_ambos_roles(self):
        for usuario in (self.docente, self.director):
            self.client.force_login(usuario)
            for tipo in ('reunion', 'otro'):
                with self.subTest(rol=usuario.rol, tipo=tipo):
                    titulo = f'{usuario.rol}-{tipo}'
                    r = self.client.post(reverse('academico:crear_evento'), {
                        'tipo': tipo, 'titulo': titulo, 'descripcion': 'Revisión privada',
                        'fecha': '2027-03-15', 'hora_inicio': '09:00', 'hora_fin': '10:30',
                        'carrera': '999', 'seccion': '999',
                    })
                    self.assertEqual(r.status_code, 302)
                    e = Evento.objects.get(creado_por=usuario, titulo=titulo)
                    self.assertIsNone(e.curso_id)
                    self.assertIsNone(e.carrera_id)
                    self.assertEqual(e.hora_inicio.isoformat(), '09:00:00')
                    self.assertEqual(e.hora_fin.isoformat(), '10:30:00')
            portal = ('academico:home_docente' if usuario.rol == 'docente'
                      else 'academico:home_administrativo')
            self.assertEqual(self.client.get(reverse(portal),
                                             {'year': 2027, 'month': 3}).status_code, 200)

    def test_evaluacion_solo_docente_y_sin_permisos_para_estudiante(self):
        datos = {'tipo': 'evaluacion', 'titulo': 'Evaluación privada', 'fecha': '2027-03-15'}
        self.client.force_login(self.docente)
        self.assertEqual(self.client.post(reverse('academico:crear_evento'), datos).status_code, 302)
        self.assertTrue(Evento.objects.filter(creado_por=self.docente, tipo='evaluacion').exists())
        for usuario in (self.director, self.estudiante):
            self.client.force_login(usuario)
            self.assertEqual(self.client.post(reverse('academico:crear_evento'), datos).status_code, 403)
        self.assertEqual(Evento.objects.filter(tipo='evaluacion').count(), 1)

    def test_datos_incorrectos_no_crean_evento(self):
        self.client.force_login(self.docente)
        for cambio in (
            {'fecha': '2027-99-99'}, {'hora_inicio': '12:00', 'hora_fin': '11:00'},
            {'hora_inicio': '', 'hora_fin': '11:00'}, {'hora_inicio': '25:00'},
            {'titulo': ''},
        ):
            with self.subTest(cambio=cambio):
                datos = {'tipo': 'reunion', 'titulo': 'Revisión', 'fecha': '2027-03-15'}
                datos.update(cambio)
                r = self.client.post(reverse('academico:crear_evento'), datos)
                self.assertEqual(r.status_code, 302)
                self.assertEqual(Evento.objects.count(), 0)

    def test_error_de_esquema_no_provoca_500_y_se_registra(self):
        self.client.force_login(self.director)
        with patch('academico.eventos_personales.Evento.objects.create',
                   side_effect=DatabaseError('simulación de columna faltante')):
            with self.assertLogs('academico.eventos_personales', level='ERROR'):
                r = self.client.post(reverse('academico:crear_evento'), {
                    'tipo': 'reunion', 'titulo': 'Prueba fallida', 'fecha': '2027-03-15'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Evento.objects.exists())
        self.assertIn('migraciones del calendario', ' '.join(str(m) for m in get_messages(r.wsgi_request)))

    def test_docente_crea_tarea_con_recordatorio(self):
        self.client.force_login(self.docente)
        r = self.client.post(reverse('academico:crear_tarea_equipo'), {
            'titulo': 'Planificar clases', 'fecha_limite': '2027-03-15',
            'hora_inicio': '15:00', 'minutos_antes': '15', 'repeticion': 'semanal',
        })
        self.assertEqual(r.status_code, 302)
        tarea = TareaEstudio.objects.get(estudiante=self.docente)
        self.assertIsNone(tarea.seccion_id)
        self.assertIn(f'configurar_tarea={tarea.pk}', r['Location'])
        self.client.force_login(self.director)
        self.assertEqual(self.client.post(reverse('academico:crear_tarea_equipo'), {
            'titulo': 'No permitido', 'fecha_limite': '2027-03-15',
            'hora_inicio': '15:00',
        }).status_code, 403)

    def test_tarea_invalida_no_500(self):
        self.client.force_login(self.docente)
        for cambios in ({'hora_inicio': '99:99'}, {'minutos_antes': 'abc'},
                        {'fecha_limite': 'sin fecha'}, {'titulo': ''}):
            with self.subTest(cambios=cambios):
                r = self.client.post(reverse('academico:crear_tarea_equipo'), {
                    'titulo': 'Tarea', 'fecha_limite': '2027-03-15',
                    'hora_inicio': '10:00', 'minutos_antes': '15', **cambios})
                self.assertEqual(r.status_code, 302)
                self.assertFalse(TareaEstudio.objects.exists())
