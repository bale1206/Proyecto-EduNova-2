from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CalendarioEstudianteHTMXTests(TestCase):
    def setUp(self):
        self.estudiante = get_user_model().objects.create_user(
            rut="12.345.678-5", email="estudiante@example.org", password="test-pass",
            first_name="Prueba", apellidos="Estudiante", rol="estudiante",
        )
        self.client.force_login(self.estudiante)
        self.url = reverse("academico:home_estudiante")

    def test_peticion_htmx_retorna_solo_calendario(self):
        for year, month, month_name in [(2026, 10, "Octubre"), (2026, 11, "Noviembre"), (2026, 12, "Diciembre"), (2027, 1, "Enero")]:
            with self.subTest(year=year, month=month):
                response = self.client.get(self.url, {"year": year, "month": month}, HTTP_HX_REQUEST="true")
                self.assertEqual(response.status_code, 200)
                content = response.content.decode()
                self.assertEqual(content.count('id="calendario-mensual"'), 1)
                self.assertIn(month_name, content)
                self.assertNotIn('Mi espacio académico', content)
                self.assertNotIn('<html', content)

    def test_navegacion_normal_muestra_pagina_completa(self):
        response = self.client.get(self.url, {"year": 2026, "month": 11})
        self.assertContains(response, 'Mi espacio académico')
        self.assertContains(response, 'Noviembre')
        self.assertContains(response, 'id="calendario-mensual"')
