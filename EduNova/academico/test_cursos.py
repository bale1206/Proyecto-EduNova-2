from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from .forms import CursoForm
from .models import Curso, Estudiante, Evento, Carrera, Asignatura


class CursosSeccionesTests(TestCase):
    def test_correlativo_compartido_por_prefijo_y_turnos(self):
        cursos = [Curso.objects.create(asignatura=asignatura, turno=turno) for asignatura, turno in [
            ('Matemática', True), ('Materiales', False), ('Matemática', False), ('Programación', True),
        ]]
        self.assertEqual([c.seccion for c in cursos], ['MAT-000-D', 'MAT-001-V', 'MAT-002-V', 'PRO-000-D'])
        cursos[1].refresh_from_db()
        self.assertIs(cursos[1].turno, False)

    def test_prefijo_normaliza_acentos_espacios_y_signos(self):
        curso = Curso.objects.create(asignatura='  Ética profesional')
        self.assertEqual(curso.seccion, 'ETI-000-D')
        with self.assertRaises(ValidationError):
            Curso.objects.create(asignatura='AB')

    def test_correlativo_se_limita_a_999(self):
        Curso.objects.bulk_create([Curso(asignatura='Matemática', turno=True, seccion='MAT-999-D')])
        with self.assertRaises(ValidationError):
            Curso.objects.create(asignatura='Materiales', turno=False)

    def test_seccion_es_unica_en_la_base_de_datos(self):
        primero = Curso.objects.create(asignatura='Matemática')
        for codigo in (primero.seccion, primero.seccion[:-1] + 'V'):
            with self.subTest(codigo=codigo), self.assertRaises(IntegrityError), transaction.atomic():
                Curso.objects.bulk_create([Curso(asignatura='Materiales', seccion=codigo)])

    def test_edicion_regenera_si_cambia_prefijo_o_turno_y_conserva_relaciones(self):
        curso = Curso.objects.create(asignatura='Matemática')
        evento = Evento.objects.create(curso=curso, titulo='Prueba', fecha='2026-10-20')
        form = CursoForm({'asignatura_catalogo': '', 'turno': 'false', 'docente_jefe': ''}, instance=curso)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(curso.seccion, 'MAT-001-V')
        curso.asignatura = 'Programación'
        curso.save()
        self.assertEqual(curso.seccion, 'PRO-000-V')
        evento.refresh_from_db()
        self.assertEqual(evento.curso_id, curso.pk)
        curso.seccion = 'CAMBIO-MANUAL'
        curso.save()
        self.assertEqual(curso.seccion, 'PRO-000-V')

    def test_formulario_no_permite_seccion_manual_y_exige_turno(self):
        self.assertNotIn('seccion', CursoForm().fields)
        form = CursoForm({'asignatura': 'Historia', 'turno': 'otro'})
        self.assertFalse(form.is_valid())
        self.assertIn('turno', form.errors)

    def test_administrativo_crea_curso_desde_su_panel(self):
        carrera = Carrera.objects.create(nombre='Carrera de prueba', escuela='Pruebas')
        materia = Asignatura.objects.create(codigo='HIS-PRUEBA', nombre='Historia')
        materia.carreras.add(carrera)
        profesor = Usuario.objects.create_user(rut='55555555-3', rol='docente')
        usuario = Usuario.objects.create_user(rut='55555555-1', rol='administrativo', carrera_dirigida=carrera)
        self.client.force_login(usuario)
        panel = self.client.get(reverse('academico:home_administrativo'))
        self.assertContains(panel, 'name="asignatura_catalogo"')
        self.assertContains(panel, 'name="turno"')
        self.assertNotContains(panel, 'name="grado_curso"')
        response = self.client.post(reverse('academico:crear_curso'), {'carrera': carrera.pk, 'asignatura_catalogo': materia.pk, 'turno': 'false', 'docentes': [profesor.pk]})
        self.assertRedirects(response, reverse('academico:home_administrativo'))
        self.assertEqual(Curso.objects.get().seccion, 'HIS-000-V')
        usuario.rol = 'docente'
        usuario.save()
        self.assertEqual(self.client.post(reverse('academico:crear_curso'), {'asignatura': 'Historia', 'turno': 'true'}).status_code, 403)

    def test_admin_de_cursos_utiliza_nuevo_formulario(self):
        admin = Usuario.objects.create_superuser(rut='55555555-2')
        self.client.force_login(admin)
        materia = Asignatura.objects.create(codigo='HIS-ADMIN', nombre='Historia')
        profesor = Usuario.objects.create_user(rut='55555555-4', rol='docente')
        url = reverse('admin:academico_curso_add')
        self.assertContains(self.client.get(url), 'name="turno"')
        response = self.client.post(url, {'asignatura_catalogo': materia.pk, 'turno': 'false', 'docentes': [profesor.pk], '_save': 'Guardar'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Curso.objects.get().seccion, 'HIS-000-V')
