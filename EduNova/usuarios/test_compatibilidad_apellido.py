"""Pruebas de regresión para el registro y la columna física `apellido`."""
from django.test import TestCase
from django.urls import reverse
from .models import Usuario


class CompatibilidadApellidoTests(TestCase):
    def test_atributo_antiguo_usa_columna_singular(self):
        self.assertEqual(Usuario._meta.get_field("apellidos").column, "apellido")

    def test_usuario_puede_guardarse_y_consultarse(self):
        user = Usuario.objects.create_user(
            rut="76543210-1", email="prueba@example.test", password="Clave-de-prueba-2026",
            rol=Usuario.Rol.DOCENTE, first_name="Ana", apellidos="García",
        )
        self.assertEqual(Usuario.objects.get(pk=user.pk).apellidos, "García")
        self.assertEqual(Usuario.objects.filter(apellidos="García").count(), 1)

    def test_login_y_registro_renderizan_sin_error_sql(self):
        self.assertEqual(self.client.get(reverse("usuarios:login")).status_code, 200)
        response = self.client.get(reverse("usuarios:registro"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apellido")
        self.assertContains(response, 'id="paso-continuar"')
        self.assertContains(response, "js/registro-roles.js")
