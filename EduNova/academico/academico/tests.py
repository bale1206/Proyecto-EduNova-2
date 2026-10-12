from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Curso, Estudiante, RegistroAsistencia


class TomarAsistenciaTests(TestCase):
	def setUp(self):
		usuario = get_user_model()
		self.docente = usuario.objects.create_user(
			rut='11.111.111-1', email='docente@example.com', password='test-pass',
			apellidos='Docente', rol='docente',
		)
		apoderado = usuario.objects.create_user(
			rut='22.222.222-2', email='apoderado@example.com', password='test-pass',
			apellidos='Apoderado', rol='apoderado',
		)
		curso = Curso.objects.create(grado_curso='1A', docente_jefe=self.docente)
		self.estudiante = Estudiante.objects.create(
			rut_estudiante='33.333.333-3', nombre_completo='Estudiante de Prueba',
			curso=curso, apoderado=apoderado,
		)
		self.client.force_login(self.docente)

	def test_post_guarda_asistencia_y_redirige_al_panel_docente(self):
		response = self.client.post(
			reverse('academico:tomar_asistencia'),
			{
				'estudiante_id': [str(self.estudiante.pk)],
				f'estado_{self.estudiante.pk}': 'presente',
			},
		)

		self.assertRedirects(response, reverse('academico:home_docente'))
		self.assertTrue(RegistroAsistencia.objects.filter(
			estudiante=self.estudiante, docente=self.docente, presente=True,
		).exists())
