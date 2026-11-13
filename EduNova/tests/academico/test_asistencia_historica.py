"""La función de tomar asistencia se retira del portal; su historial no se borra."""
from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse


class AsistenciaRetiradaTests(SimpleTestCase):
    def test_ya_no_existen_vistas_de_asistencia_para_los_perfiles(self):
        for nombre in ('tomar_asistencia', 'analitica_carrera'):
            with self.subTest(nombre=nombre), self.assertRaises(NoReverseMatch):
                reverse('academico:' + nombre)

    def test_observaciones_conservan_carga_de_estudiantes(self):
        # El endpoint se comparte con el registro de observaciones y no debe
        # desaparecer al retirar la función de asistencia.
        self.assertTrue(reverse('academico:ajax_cargar_estudiantes'))
