from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from .forms import CursoForm
from .models import Curso, Estudiante, Evento


class CursosSeccionesTests(TestCase):
    def test_correlativo_compartido_por_prefijo_y_turnos(self):
        cursos = [Curso.objects.create(asignatura=asignatura, turno=turno) for asignatura, turno in [
            ('Matemática', True), ('Materiales', False), ('Matemática', False), ('Programación', True),
        ]]
        self.assertEqual([c.seccion for c in cursos], ['MAT-000D', 'MAT-001V', 'MAT-002V', 'PRO-000D'])
        cursos[1].refresh_from_db()
        self.assertIs(cursos[1].turno, False)

    def test_prefijo_normaliza_acentos_espacios_y_signos(self):
        curso = Curso.objects.create(asignatura='  Ética profesional')
        self.assertEqual(curso.seccion, 'ETI-000D')
        with self.assertRaises(ValidationError):
            Curso.objects.create(asignatura='AB')

    def test_correlativo_supera_tres_digitos_sin_duplicarse(self):
        Curso.objects.bulk_create([Curso(asignatura='Matemática', turno=True, seccion='MAT-999D')])
        self.assertEqual(Curso.objects.create(asignatura='Materiales', turno=False).seccion, 'MAT-1000V')

    def test_seccion_es_unica_en_la_base_de_datos(self):
        primero = Curso.objects.create(asignatura='Matemática')
        for codigo in (primero.seccion, primero.seccion[:-1] + 'V'):
            with self.subTest(codigo=codigo), self.assertRaises(IntegrityError), transaction.atomic():
                Curso.objects.bulk_create([Curso(asignatura='Materiales', seccion=codigo)])

    def test_edicion_regenera_si_cambia_prefijo_o_turno_y_conserva_relaciones(self):
        curso = Curso.objects.create(asignatura='Matemática')
        evento = Evento.objects.create(curso=curso, titulo='Prueba', fecha='2026-10-20')
        form = CursoForm({'asignatura': 'Matemática', 'turno': 'false', 'docente_jefe': ''}, instance=curso)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(curso.seccion, 'MAT-001V')
        curso.asignatura = 'Programación'
        curso.save()
        self.assertEqual(curso.seccion, 'PRO-000V')
        evento.refresh_from_db()
        self.assertEqual(evento.curso_id, curso.pk)
        curso.seccion = 'CAMBIO-MANUAL'
        curso.save()
        self.assertEqual(curso.seccion, 'PRO-000V')

    def test_formulario_no_permite_seccion_manual_y_exige_turno(self):
        self.assertNotIn('seccion', CursoForm().fields)
        form = CursoForm({'asignatura': 'Historia', 'turno': 'otro'})
        self.assertFalse(form.is_valid())
        self.assertIn('turno', form.errors)

    def test_administrativo_crea_curso_desde_su_panel(self):
        usuario = Usuario.objects.create_user(rut='55555555-1', rol='administrativo')
        self.client.force_login(usuario)
        panel = self.client.get(reverse('academico:home_administrativo'))
        self.assertContains(panel, 'name="asignatura"')
        self.assertContains(panel, 'name="turno"')
        self.assertNotContains(panel, 'name="grado_curso"')
        response = self.client.post(reverse('academico:crear_curso'), {'asignatura': 'Historia', 'turno': 'false', 'docente_jefe': ''})
        self.assertRedirects(response, reverse('academico:home_administrativo'))
        self.assertEqual(Curso.objects.get().seccion, 'HIS-000V')
        usuario.rol = 'docente'
        usuario.save()
        self.assertEqual(self.client.post(reverse('academico:crear_curso'), {'asignatura': 'Historia', 'turno': 'true'}).status_code, 403)

    def test_admin_de_cursos_utiliza_nuevo_formulario(self):
        admin = Usuario.objects.create_superuser(rut='55555555-2')
        self.client.force_login(admin)
        url = reverse('admin:academico_curso_add')
        self.assertContains(self.client.get(url), 'name="turno"')
        response = self.client.post(url, {'asignatura': 'Historia', 'turno': 'false', 'docente_jefe': '', '_save': 'Guardar'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Curso.objects.get().seccion, 'HIS-000V')
