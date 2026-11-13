"""Comprueba que la guía para XLSX esté visible a los dos perfiles."""
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario


class GuiaHorarioTests(TestCase):
    def test_guia_en_importacion_para_estudiante_y_docente(self):
        for indice, (rol, correo) in enumerate((
            ('estudiante', 'guia@duocuc.cl'),
            ('docente', 'guia@profesor.duoc.cl'),
        )):
            usuario = Usuario.objects.create_user(
                ('12345678-5' if indice == 0 else '9876543-3'), correo, 'ClaveSegura123!', rol=rol,
                first_name='Prueba', apellidos='Guia')
            self.client.force_login(usuario)
            respuesta = self.client.get(reverse('academico:importar_horario'))
            self.assertContains(respuesta, 'Cómo completar tu horario: paso a paso')
            self.assertContains(respuesta, '2027-03-01')
            self.assertContains(respuesta, 'Exportar mi horario XLSX')
            self.assertContains(respuesta, 'id="guia-horario"')
