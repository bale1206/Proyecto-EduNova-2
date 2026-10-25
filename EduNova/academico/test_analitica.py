from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Usuario
from .models import (Asignatura, Asistencia, Carrera, Curso, Estudiante,
                     MarcaAsistencia, RegistroAsistencia, SesionClase)


class PorcentajeAsistenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Pruebas de asistencia', escuela='Pruebas')
        cls.otra = Carrera.objects.create(nombre='Otra carrera de asistencia', escuela='Pruebas')
        cls.materia = Asignatura.objects.create(codigo='TEST-ASIS', nombre='Matemática de prueba')
        cls.materia.carreras.add(cls.carrera, cls.otra)
        cls.seccion = Curso.objects.create(asignatura_catalogo=cls.materia)
        cls.segunda = Curso.objects.create(asignatura_catalogo=cls.materia, turno=False)
        cls.docente = Usuario.objects.create_user(rut='88000000-1', rol='docente')
        cls.director = Usuario.objects.create_user(rut='88000000-2', rol='administrativo', carrera_dirigida=cls.carrera)
        cls.cuenta = Usuario.objects.create_user(rut='88000000-3', rol='estudiante', curso=cls.seccion)
        cls.alumno = Estudiante.objects.get(usuario=cls.cuenta)
        cls.hoy = timezone.localdate()

    def panel(self, **filtros):
        self.client.force_login(self.director)
        return self.client.get(reverse('academico:analitica_carrera'), {
            'carrera': self.carrera.pk, 'asignatura': self.materia.pk, **filtros,
        })

    def marca(self, presente, dias=0, alumno=None, seccion=None):
        sesion, _ = SesionClase.objects.get_or_create(
            seccion=seccion or self.seccion, fecha=self.hoy - timedelta(days=dias),
            defaults={'docente': self.docente},
        )
        return MarcaAsistencia.objects.create(sesion=sesion, estudiante=alumno or self.alumno, presente=presente)

    def test_registro_publico_sin_carrera_calcula_y_grafica_decimal(self):
        self.marca(True)
        self.marca(True, dias=1)
        self.marca(False, dias=2)
        respuesta = self.panel()
        self.assertEqual(respuesta.context['porcentaje'], 66.7)
        self.assertEqual(respuesta.context['total_registros'], 3)
        self.assertEqual(respuesta.context['sin_carrera'], 3)
        self.assertContains(respuesta, 'width:66.7%')
        self.assertContains(respuesta, 'sin carrera asignada')

    def test_historial_se_corrige_sin_duplicados_y_marca_tiene_prioridad(self):
        Asistencia.objects.create(estudiante=self.alumno, fecha=self.hoy, estado='ausente')
        RegistroAsistencia.objects.create(estudiante=self.alumno, seccion=self.seccion, docente=self.docente, presente=True)
        RegistroAsistencia.objects.create(estudiante=self.alumno, seccion=self.seccion, docente=self.docente, presente=False)
        respuesta = self.panel()
        self.assertEqual(respuesta.context['total_registros'], 1)
        self.assertEqual(respuesta.context['porcentaje'], 0.0)
        self.marca(True)
        respuesta = self.panel()
        self.assertEqual(respuesta.context['total_registros'], 1)
        self.assertEqual(respuesta.context['porcentaje'], 100.0)

    def test_registro_sin_seccion_y_estados_escolares(self):
        RegistroAsistencia.objects.create(estudiante=self.alumno, docente=self.docente, presente=False)
        Asistencia.objects.create(estudiante=self.alumno, fecha=self.hoy - timedelta(days=1), estado='atraso')
        Asistencia.objects.create(estudiante=self.alumno, fecha=self.hoy - timedelta(days=2), estado='justificado')
        respuesta = self.panel()
        self.assertEqual(respuesta.context['total_registros'], 3)
        self.assertEqual(respuesta.context['presentes'], 1)
        self.assertEqual(respuesta.context['ausentes'], 2)
        self.assertEqual(respuesta.context['porcentaje'], 33.3)

    def test_historial_ambiguo_no_se_atribuye_a_varias_secciones(self):
        self.alumno.secciones.add(self.segunda)
        RegistroAsistencia.objects.create(estudiante=self.alumno, docente=self.docente, presente=True)
        Asistencia.objects.create(estudiante=self.alumno, fecha=self.hoy, estado='presente')
        self.assertIsNone(self.panel().context['porcentaje'])
        RegistroAsistencia.objects.create(estudiante=self.alumno, seccion=self.segunda, docente=self.docente, presente=True)
        self.assertEqual(self.panel(seccion=self.segunda.pk).context['porcentaje'], 100.0)
        self.assertIsNone(self.panel(seccion=self.seccion.pk).context['porcentaje'])

    def test_total_ponderado_y_carrera_conocida_respetada(self):
        self.marca(True)
        self.marca(True, dias=1)
        self.marca(True, dias=2)
        self.marca(False, seccion=self.segunda)
        ajeno = Estudiante.objects.create(rut_estudiante='88000000-4', nombre_completo='Otra carrera', carrera=self.otra, curso=self.seccion)
        self.marca(False, alumno=ajeno)
        respuesta = self.panel()
        self.assertEqual(respuesta.context['total_registros'], 4)
        self.assertEqual(respuesta.context['porcentaje'], 75.0)
        self.assertEqual([d['porcentaje'] for d in respuesta.context['detalle']], [100.0, 0.0])
        self.assertEqual(self.panel(seccion=self.segunda.pk).context['porcentaje'], 0.0)

    def test_sin_registros_no_divide_por_cero(self):
        respuesta = self.panel()
        self.assertIsNone(respuesta.context['porcentaje'])
        self.assertEqual(respuesta.context['total_registros'], 0)
        self.assertContains(respuesta, 'Todavía no se registró asistencia')

    def test_historial_de_seccion_eliminada_no_se_reasigna(self):
        marca = self.marca(True)
        RegistroAsistencia.objects.create(estudiante=self.alumno, seccion=self.seccion, docente=self.docente, presente=True)
        self.seccion.delete()
        self.alumno.curso = self.segunda
        self.alumno.save()
        self.alumno.secciones.add(self.segunda)
        marca.refresh_from_db()
        self.assertIsNone(marca.sesion.seccion_id)
        self.assertIsNone(self.panel(seccion=self.segunda.pk).context['porcentaje'])

    def test_estudiante_no_tiene_acceso_al_panel(self):
        self.client.force_login(self.cuenta)
        self.assertEqual(self.client.get(reverse('academico:analitica_carrera')).status_code, 403)

    def test_secciones_sin_catalogo_tambien_calculan(self):
        historica = Curso.objects.create(asignatura='Lenguaje histórico')
        self.alumno.curso = historica
        self.alumno.save()
        self.alumno.secciones.set([historica])
        RegistroAsistencia.objects.create(estudiante=self.alumno, docente=self.docente, presente=True)
        self.marca(False, dias=1, seccion=historica)
        self.marca(True)  # La sección del catálogo no pertenece a esta selección.
        respuesta = self.panel(carrera='historico', asignatura=historica.asignatura)
        self.assertEqual(respuesta.context['total_registros'], 2)
        self.assertEqual(respuesta.context['porcentaje'], 50.0)
        self.assertContains(respuesta, 'Historial de todas las carreras')
        self.assertEqual(list(respuesta.context['secciones_disponibles']), [historica])
