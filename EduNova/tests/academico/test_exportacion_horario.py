"""Pruebas nuevas, aisladas de los datos reales de la institución."""
from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from academico.horario_personal import leer_horario
from academico.models import BloqueHorarioPersonal
from usuarios.models import Usuario


class ExportacionHorarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = Usuario.objects.create_user(
            '12345678-5', 'exportar-estudiante@duocuc.cl', 'ClaveSegura123!',
            rol='estudiante', first_name='Estudiante', apellidos='Uno')
        cls.docente = Usuario.objects.create_user(
            '9876543-3', 'exportar-docente@profesor.duoc.cl', 'ClaveSegura123!',
            rol='docente', first_name='Docente', apellidos='Dos')
        cls.director = Usuario.objects.create_user(
            '11111111-1', 'exportar-director@duoc.cl', 'ClaveSegura123!',
            rol='administrativo', first_name='Director', apellidos='Tres')
        BloqueHorarioPersonal.objects.create(
            usuario=cls.estudiante, asignatura='Programación', dia_semana=1,
            hora_inicio=time(8, 30), hora_fin=time(9, 50),
            fecha_inicio=date(2027, 3, 1), fecha_fin=date(2027, 7, 15),
            sala='Sala 204', docente='Ejemplo')
        BloqueHorarioPersonal.objects.create(
            usuario=cls.docente, asignatura='Asignatura privada de docente',
            dia_semana=3, hora_inicio=time(10, 0), hora_fin=time(11, 20),
            fecha_inicio=date(2027, 3, 1), fecha_fin=date(2027, 7, 15))

    def test_solo_usuario_autorizado_puede_exportar(self):
        url = reverse('academico:exportar_horario')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.director)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_xlsx_del_estudiante_se_puede_reimportar(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('academico:exportar_horario'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Cache-Control'], 'private, no-store')
        self.assertIn('mi-horario-edunova.xlsx', respuesta['Content-Disposition'])
        bloques = leer_horario(respuesta.content, 'mi-horario-edunova.xlsx')
        self.assertEqual(len(bloques), 1)
        self.assertEqual(bloques[0]['asignatura'], 'Programación')
        self.assertEqual(bloques[0]['hora_inicio'], '08:30:00')
        self.assertEqual(bloques[0]['fecha_fin'], '2027-07-15')
        self.assertNotIn('Asignatura privada de docente', str(bloques))
        self.assertContains(self.client.get(reverse('academico:home_estudiante')),
                            'Exportar mi horario XLSX')

    def test_docente_solo_ve_su_horario(self):
        self.client.force_login(self.docente)
        respuesta = self.client.get(reverse('academico:exportar_horario'))
        self.assertEqual(respuesta.status_code, 200)
        nombres = [b['asignatura'] for b in leer_horario(respuesta.content, 'horario.xlsx')]
        self.assertEqual(nombres, ['Asignatura privada de docente'])
        self.assertContains(self.client.get(reverse('academico:home_docente')),
                            'Exportar mi horario XLSX')
