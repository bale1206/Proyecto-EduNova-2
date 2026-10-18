from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from academico.models import Curso, Estudiante, Evento
from comunicacion.services import cursos_relacionados
from .forms import RegistroForm
from .models import Usuario


class UsuarioCursoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.curso = Curso.objects.create(asignatura='Matemática')
        cls.otro_curso = Curso.objects.create(asignatura='Historia', turno=False)

    def datos(self, **extra):
        return {'rut': '12345678-9', 'first_name': 'Ana', 'apellidos': 'Pérez', 'email': 'ana@example.org',
                'telefono': '', 'rol': 'estudiante', 'curso': self.curso.pk,
                'password1': 'UnaClaveSegura!2026', 'password2': 'UnaClaveSegura!2026', **extra}

    def test_estudiante_debe_elegir_curso_valido(self):
        for valor in ('', '99999'):
            form = RegistroForm(self.datos(curso=valor))
            self.assertFalse(form.is_valid())
            self.assertIn('curso', form.errors)
        usuario = Usuario(rut='22222222-1', rol='estudiante')
        with self.assertRaises(ValidationError):
            usuario.clean()

    def test_registro_crea_usuario_y_ficha_con_mismo_curso(self):
        response = self.client.post(reverse('usuarios:registro'), self.datos())
        usuario = Usuario.objects.get(rut='12345678-9')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuario.curso_id, self.curso.pk)
        perfil = usuario.perfil_estudiante
        self.assertEqual(perfil.curso_id, self.curso.pk)
        self.assertEqual(perfil.nombre_completo, 'Ana Pérez')
        self.assertIsNone(perfil.apoderado_id)
        self.assertEqual(list(cursos_relacionados(usuario)), [self.curso])
        Evento.objects.create(curso=self.curso, titulo='Evaluación de curso', fecha='2026-10-20')
        self.assertContains(self.client.get(reverse('academico:home_estudiante'), {'year': 2026, 'month': 10}), 'Evaluación de curso')

    def test_docente_no_necesita_curso_y_no_conserva_valor_enviado(self):
        for valor in ('', self.curso.pk):
            form = RegistroForm(self.datos(rol='docente', curso=valor))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertIsNone(form.cleaned_data['curso'])
        usuario = form.save()
        self.assertIsNone(usuario.curso_id)
        self.assertFalse(Estudiante.objects.filter(usuario=usuario).exists())

    def test_estudiante_puede_usar_ficha_existente_sin_perder_historial(self):
        perfil = Estudiante.objects.create(rut_estudiante='12345678-9', nombre_completo='Anterior', curso=self.otro_curso)
        form = RegistroForm(self.datos())
        self.assertTrue(form.is_valid(), form.errors)
        usuario = form.save()
        perfil.refresh_from_db()
        self.assertEqual(usuario.perfil_estudiante.pk, perfil.pk)
        self.assertEqual(perfil.curso_id, self.curso.pk)

    def test_cambiar_curso_desde_usuario_o_ficha_mantiene_sincronizacion(self):
        usuario = Usuario.objects.create_user(rut='12345678-9', rol='estudiante', curso=self.curso)
        usuario.curso = self.otro_curso
        usuario.save(update_fields=['curso'])
        perfil = Estudiante.objects.get(usuario=usuario)
        self.assertEqual(perfil.curso_id, self.otro_curso.pk)
        perfil.curso = self.curso
        perfil.save()
        usuario.refresh_from_db()
        self.assertEqual(usuario.curso_id, self.curso.pk)
        self.curso.delete()
        usuario.refresh_from_db()
        self.assertIsNone(usuario.curso_id)

    def test_admin_exige_curso_al_crear_y_editar_estudiante(self):
        admin = Usuario.objects.create_superuser(rut='99999999-1')
        self.client.force_login(admin)
        url = reverse('admin:usuarios_usuario_add')
        self.assertContains(self.client.get(url), 'name="curso"')
        response = self.client.post(url, self.datos(curso=''))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Debes asociar al estudiante a una sección.')
        self.assertFalse(Usuario.objects.filter(rut='12345678-9').exists())
        self.assertEqual(self.client.post(url, self.datos()).status_code, 302)
        alumno = Usuario.objects.get(rut='12345678-9')
        self.assertEqual(alumno.perfil_estudiante.curso_id, self.curso.pk)
        editar = reverse('admin:usuarios_usuario_change', args=[alumno.pk])
        datos = self.datos(curso=self.otro_curso.pk)
        datos.pop('password1'); datos.pop('password2')
        datos['is_active'] = 'on'
        response = self.client.post(editar, datos)
        self.assertEqual(response.status_code, 302)
        alumno.refresh_from_db()
        self.assertEqual(alumno.curso_id, self.otro_curso.pk)
        self.assertEqual(Estudiante.objects.get(usuario=alumno).curso_id, self.otro_curso.pk)
        response = self.client.post(editar, {**datos, 'curso': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Debes asociar al estudiante a una sección.')

    def test_formulario_de_registro_contiene_curso_una_vez(self):
        response = self.client.get(reverse('usuarios:registro'))
        self.assertContains(response, 'id="curso-estudiante"', count=1)
        self.assertContains(response, 'name="curso"', count=1)
        self.assertContains(response, 'MAT-000-D')
