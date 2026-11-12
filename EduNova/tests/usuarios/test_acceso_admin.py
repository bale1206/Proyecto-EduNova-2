from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario


class AccesoAdministradorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_superuser(
            rut='12345678-9', email='admin@example.com', password='PruebaSegura1234!',
            first_name='Admin', apellidos='Prueba',
        )

    def test_login_del_portal_abre_admin_sin_importador(self):
        response = self.client.post(reverse('usuarios:login'), {
            'rut': self.admin.rut, 'password': 'PruebaSegura1234!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse('admin:index'))
        self.assertNotContains(response, 'Abrir importador académico')
        self.assertNotContains(response, 'importaciones-academicas')

    def test_login_directo_del_admin_abre_inicio(self):
        response = self.client.post(reverse('admin:login'), {
            'username': self.admin.rut, 'password': 'PruebaSegura1234!',
            'next': reverse('admin:index'),
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse('admin:index'))
