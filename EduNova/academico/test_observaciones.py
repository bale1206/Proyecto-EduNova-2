from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.messages import get_messages
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from comunicacion.models import MensajeComunicacion
from comunicacion.services import mensajes_no_leidos
from .forms import ObservacionForm, ActualizarObservacionForm
from .models import Curso, Estudiante, Observacion, ObservacionComportamiento


class ObservacionesSancionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.funcionario = Usuario.objects.create_user(rut='10000000-1', rol='administrativo')
        cls.docente = Usuario.objects.create_user(rut='10000000-2', rol='docente')
        cls.apoderado = Usuario.objects.create_user(rut='10000000-3', rol='apoderado')
        cls.alumno = Usuario.objects.create_user(rut='10000000-4', rol='estudiante')
        cls.otro = Usuario.objects.create_user(rut='10000000-5', rol='estudiante')
        cls.curso = Curso.objects.create(grado_curso='1A', docente_jefe=cls.docente)
        cls.estudiante = Estudiante.objects.create(
            rut_estudiante=cls.alumno.rut, nombre_completo='Alumno Uno',
            curso=cls.curso, apoderado=cls.apoderado, usuario=cls.alumno,
        )
        cls.obs = ObservacionComportamiento.objects.create(
            docente=cls.docente, curso=cls.curso, asunto='Incidente',
            descripcion='Descripción del incidente', tipo_observacion='SANCION',
        )
        cls.obs.estudiantes.add(cls.estudiante)

    def setUp(self):
        self.client.force_login(self.funcionario)
        self.url = reverse('academico:actualizar_observacion', args=[self.obs.pk])
        self.datos = {'tipo_observacion': 'SANCION', 'estado': 'EN_PROCESO', 'resolucion': 'Conversación de seguimiento'}

    def test_opciones_y_rechazo_de_tipos_retirados(self):
        for form_class in (ObservacionForm, ActualizarObservacionForm):
            choices = dict(form_class().fields['tipo_observacion'].choices)
            self.assertEqual(choices['SANCION'], 'Sanción')
            self.assertNotIn('POSITIVA', choices)
            self.assertNotIn('NEGATIVA', choices)
        for tipo in ('POSITIVA', 'NEGATIVA'):
            response = self.client.post(self.url, {**self.datos, 'tipo_observacion': tipo, 'notificar_apoderado': 'on'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('tipo_observacion', response.context['form'].errors)
        self.assertFalse(MensajeComunicacion.objects.exists())

    def test_notifica_solo_al_estudiante_y_puede_leerlo(self):
        response = self.client.post(self.url, {**self.datos, 'notificar_apoderado': 'on'})
        self.assertRedirects(response, reverse('academico:lista_observaciones'))
        mensaje = MensajeComunicacion.objects.get()
        self.assertEqual(mensaje.destinatario, self.alumno)
        self.assertEqual(mensaje.remitente, self.funcionario)
        self.assertIn('Sanción', mensaje.cuerpo_mensaje)
        self.assertIn(self.datos['resolucion'], mensaje.cuerpo_mensaje)
        self.assertEqual(mensajes_no_leidos(self.alumno).count(), 1)
        self.assertFalse(mensajes_no_leidos(self.apoderado).exists())
        self.assertFalse(mensajes_no_leidos(self.otro).exists())
        self.client.force_login(self.alumno)
        self.assertContains(self.client.get(reverse('comunicacion:bandeja')), mensaje.asunto)
        self.assertContains(self.client.get(reverse('comunicacion:panel_notificaciones')), mensaje.asunto)
        self.assertEqual(self.client.get(reverse('comunicacion:detalle_mensaje', args=[mensaje.pk])).status_code, 200)
        self.assertFalse(mensajes_no_leidos(self.alumno).exists())
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(reverse('comunicacion:detalle_mensaje', args=[mensaje.pk])).status_code, 404)

    def test_sin_marcar_no_notifica(self):
        self.client.post(self.url, self.datos)
        self.obs.refresh_from_db()
        self.assertEqual(self.obs.resolucion, self.datos['resolucion'])
        self.assertFalse(MensajeComunicacion.objects.exists())

    def test_estudiantes_sin_cuenta_o_con_rol_incorrecto(self):
        for usuario in (None, self.docente):
            with self.subTest(usuario=usuario):
                self.estudiante.usuario = usuario
                self.estudiante.save()
                response = self.client.post(self.url, {**self.datos, 'notificar_apoderado': 'on'})
                avisos = [str(m) for m in get_messages(response.wsgi_request)]
                self.assertTrue(any('no tienen una cuenta con rol estudiante' in m for m in avisos))
                self.assertFalse(MensajeComunicacion.objects.exists())

    def test_notifica_a_cada_estudiante_asociado(self):
        segundo = Estudiante.objects.create(rut_estudiante=self.otro.rut, nombre_completo='Alumno Dos', curso=self.curso, apoderado=self.apoderado, usuario=self.otro)
        self.obs.estudiantes.add(segundo)
        self.client.post(self.url, {**self.datos, 'notificar_apoderado': 'on'})
        self.assertSetEqual(set(MensajeComunicacion.objects.values_list('destinatario_id', flat=True)), {self.alumno.pk, self.otro.pk})

    def test_error_al_enviar_revierte_actualizacion(self):
        with patch('academico.views.MensajeComunicacion.objects.create', side_effect=RuntimeError('Error de escritura')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, {**self.datos, 'notificar_apoderado': 'on'})
        self.obs.refresh_from_db()
        self.assertEqual(self.obs.estado, 'NO_VISTA')
        self.assertFalse(MensajeComunicacion.objects.exists())

    def test_panel_muestra_sancion_y_oculta_positivas_historicas(self):
        antigua = ObservacionComportamiento.objects.create(docente=self.docente, curso=self.curso, asunto='Positiva histórica', descripcion='Historial', tipo_observacion='POSITIVA')
        response = self.client.get(reverse('academico:lista_observaciones'))
        self.assertContains(response, 'Sanción')
        self.assertNotContains(response, antigua.asunto)
        self.assertTrue(ObservacionComportamiento.objects.filter(pk=antigua.pk).exists())
        self.assertContains(self.client.get(self.url), 'Avisar al estudiante')

    def test_migracion_convierte_negativas_y_conserva_historico(self):
        ObservacionComportamiento.objects.filter(pk=self.obs.pk).update(tipo_observacion='NEGATIVA')
        anterior = Observacion.objects.create(estudiante=self.estudiante, docente_o_inspector=self.docente, tipo='negativa', contenido_texto='Historial')
        positiva = Observacion.objects.create(estudiante=self.estudiante, docente_o_inspector=self.docente, tipo='positiva', contenido_texto='Historial positivo')
        migration = import_module('academico.migrations.0007_sanciones_observaciones')
        migration.convertir_negativas(apps, SimpleNamespace(connection=connection))
        anterior.refresh_from_db()
        self.obs.refresh_from_db()
        positiva.refresh_from_db()
        self.assertEqual(anterior.tipo, 'sancion')
        self.assertEqual(self.obs.tipo_observacion, 'SANCION')
        self.assertEqual(positiva.tipo, 'positiva')
        migration.restaurar_negativas(apps, SimpleNamespace(connection=connection))
        anterior.refresh_from_db()
        self.obs.refresh_from_db()
        self.assertEqual(anterior.tipo, 'negativa')
        self.assertEqual(self.obs.tipo_observacion, 'NEGATIVA')
