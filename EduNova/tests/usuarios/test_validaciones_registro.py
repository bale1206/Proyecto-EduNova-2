"""Pruebas de las reglas sin tocar PostgreSQL/Supabase."""
import unittest
from usuarios.validaciones_registro import validar_y_normalizar_rut, password_minimo_registro


class ValidacionRutTest(unittest.TestCase):
    def test_generador_matematicamente_valido(self):
        self.assertEqual(validar_y_normalizar_rut('12.345.678-5'), '12345678-5')
        self.assertEqual(validar_y_normalizar_rut('22.222.222-2'), '22222222-2')

    def test_rut_erroneo(self):
        for rut in ('12.345.678-9', '12.222.222-2', 'abcdefgh-5', '12345678', '12.345.678-K'):
            with self.subTest(rut=rut):
                self.assertIsNone(validar_y_normalizar_rut(rut))

    def test_password_minima(self):
        self.assertTrue(password_minimo_registro('Abcd1234'))
        self.assertFalse(password_minimo_registro('corta'))
        self.assertFalse(password_minimo_registro('12345678'))
        self.assertFalse(password_minimo_registro('abcdefgh'))


if __name__ == '__main__':
    unittest.main()
