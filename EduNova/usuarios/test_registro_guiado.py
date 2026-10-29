from datetime import date
from django.test import SimpleTestCase
from .registro_guiado import periodo_actual


class PeriodoGuiadoTests(SimpleTestCase):
    def test_primer_semestre(self):
        self.assertEqual(periodo_actual(date(2026, 3, 1)), (2026, 1))
        self.assertEqual(periodo_actual(date(2026, 7, 31)), (2026, 1))

    def test_segundo_semestre(self):
        self.assertEqual(periodo_actual(date(2026, 8, 1)), (2026, 2))
        self.assertEqual(periodo_actual(date(2026, 12, 31)), (2026, 2))

    def test_fuera_periodo(self):
        self.assertEqual(periodo_actual(date(2026, 2, 1)), (2026, None))
