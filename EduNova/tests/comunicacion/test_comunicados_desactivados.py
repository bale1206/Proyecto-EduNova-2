"""Se oculta el botón de comunicado y se bloquea también su URL directa."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ComunicadosDesactivadosTests(TestCase):
    def test_docentes_estudiantes_directores_no_pueden_publicar(self):
        Usuario = get_user_model()
        for numero, rol in enumerate(('docente', 'estudiante', 'administrativo')):
            with self.subTest(rol=rol):
                usuario = Usuario.objects.create_user(
                    rut=f'1600000{numero}-0', email=f'test{numero}@example.org',
                    password='ClaveDePruebaLarga!2026', rol=rol,
                    first_name='Usuario', apellidos='Prueba',
                )
                self.client.force_login(usuario)
                ruta = reverse('comunicacion:enviar_comunicado')
                self.assertEqual(self.client.get(ruta).status_code, 403)
                self.assertEqual(self.client.post(ruta, data={'asunto': 'No autorizado'}).status_code, 403)
                self.client.logout()
