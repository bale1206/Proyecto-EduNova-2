"""Regresiones del importador privado. Ejecutar en PostgreSQL de pruebas aislado."""
from io import BytesIO
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase as PythonTestCase

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from usuarios.models import Usuario
from .importacion_archivos import leer_malla, leer_oferta
from .models import (Carrera, Curso, HorarioSeccion, ImportacionAcademica,
                     PlanEstudio, PlanAsignatura)

MALLA = (b'codigo_asignatura;nombre_asignatura;anio_curricular;semestre_curricular\n'
         b'PRO1001;Fundamentos de Programacion;1;1\n')
OFERTA = ('Sede;Carrera;Plan;Jornada;Sigla Asignatura;Nombre Asignatura;Nivel;Sección;Horario;Docente\n'
          'ANTONIO VARAS;Ingeniería en Informática;2026;Diurno;PRO1001;Fundamentos de Programación;1;PRO1001-006D;Lu 8:31:00 - 9:50:00;Docente Ejemplo\n'
          'ANTONIO VARAS;Ingeniería en Informática;2026;Diurno;PRO1001;Fundamentos de Programación;1;PRO1001-006D;Ma 10:01:00 - 11:20:00;Docente Ejemplo\n').encode('utf-8')


class LecturaDocumentosTests(PythonTestCase):
    def test_malla_estructurada(self):
        data = leer_malla(MALLA, 'malla.csv')
        self.assertFalse(data['errores'])
        self.assertEqual(data['filas'][0]['anio'], 1)

    def test_oferta_agrupa_bloques_por_seccion(self):
        data = leer_oferta(OFERTA, 'oferta.csv')
        self.assertFalse(data['errores'])
        self.assertEqual(data['total'], 2)
        self.assertEqual(len(data['grupos']), 1)
        self.assertEqual(len(next(iter(data['grupos'].values()))['horarios']), 2)


class ImportacionPrivadaTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.override = override_settings(BASE_DIR=Path(self.tmp.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.carrera = Carrera.objects.create(nombre='Ingeniería en Informática', escuela='Informática')
        self.admin = Usuario.objects.create_superuser(
            rut='12345678-9', email='admin@edunova.local', password='PruebaSegura1234!',
            first_name='Admin', apellidos='Ejemplo')
        self.url = reverse('edunova_importaciones_admin')

    def test_solo_superusuario(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        normal = Usuario.objects.create_user(
            rut='98765432-1', email='estudiante@ejemplo.cl', password='PruebaSegura1234!',
            first_name='Usuario', apellidos='Comun', rol=Usuario.Rol.ESTUDIANTE)
        self.client.force_login(normal)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_importa_malla_solo_tras_confirmacion(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'accion':'previsualizar', 'tipo':'malla', 'carrera':str(self.carrera.pk),
            'ingreso':'2026', 'mencion':'',
            'archivo':SimpleUploadedFile('malla.csv', MALLA, content_type='text/csv'),
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PlanEstudio.objects.count(), 0)
        resp = self.client.post(self.url, {'accion':'aplicar', 'confirmado':'si'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PlanEstudio.objects.count(), 1)
        self.assertEqual(PlanAsignatura.objects.count(), 1)
        self.assertEqual(ImportacionAcademica.objects.count(), 1)

    def test_oferta_no_duplica_seccion_por_bloques(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, {
            'accion':'previsualizar', 'tipo':'oferta', 'anio':'2026', 'semestre':'2',
            'archivo':SimpleUploadedFile('oferta.csv', OFERTA, content_type='text/csv'),
        })
        self.assertEqual(resp.status_code, 200)
        career_name = 'Ingeniería en Informática'
        campo = 'map_' + hashlib.sha256(career_name.encode()).hexdigest()[:16]
        resp = self.client.post(self.url, {'accion':'aplicar', 'confirmado':'si', campo:str(self.carrera.pk)})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Curso.objects.filter(codigo_institucional='PRO1001-006D').count(), 1)
        self.assertEqual(HorarioSeccion.objects.count(), 2)
        self.assertEqual(Curso.objects.filter(periodo_academico__anio=2026, periodo_academico__semestre=2).count(), 1)

    def test_oferta_puede_crear_carrera_faltante_al_confirmar(self):
        self.client.force_login(self.admin)
        fuente = 'Ecoturismo'
        oferta = OFERTA.replace('Ingeniería en Informática'.encode(), fuente.encode())
        response = self.client.post(self.url, {
            'accion': 'previsualizar', 'tipo': 'oferta', 'anio': '2026', 'semestre': '2',
            'archivo': SimpleUploadedFile('oferta.csv', oferta, content_type='text/csv'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Carrera.objects.filter(nombre=fuente).exists())
        clave = hashlib.sha256(fuente.encode()).hexdigest()[:16]
        response = self.client.post(self.url, {
            'accion': 'aplicar', 'confirmado': 'si',
            'map_' + clave: '__crear__',
            'nuevo_nombre_' + clave: fuente,
            'nueva_escuela_' + clave: 'Turismo y Hospitalidad',
        })
        self.assertEqual(response.status_code, 302)
        creada = Carrera.objects.get(nombre=fuente)
        self.assertEqual(creada.escuela, 'Turismo y Hospitalidad')
        self.assertTrue(Curso.objects.filter(asignatura_catalogo__carreras=creada).exists())
        self.assertEqual(ImportacionAcademica.objects.get().resumen['carreras_nuevas'], 1)

    def test_no_crea_carrera_con_escuela_vacia(self):
        self.client.force_login(self.admin)
        fuente = 'Ecoturismo'
        oferta = OFERTA.replace('Ingeniería en Informática'.encode(), fuente.encode())
        self.client.post(self.url, {
            'accion': 'previsualizar', 'tipo': 'oferta', 'anio': '2026', 'semestre': '2',
            'archivo': SimpleUploadedFile('oferta.csv', oferta, content_type='text/csv'),
        })
        clave = hashlib.sha256(fuente.encode()).hexdigest()[:16]
        response = self.client.post(self.url, {
            'accion': 'aplicar', 'confirmado': 'si',
            'map_' + clave: '__crear__',
            'nuevo_nombre_' + clave: fuente, 'nueva_escuela_' + clave: '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Indica una escuela válida')
        self.assertFalse(Carrera.objects.filter(nombre=fuente).exists())
        self.assertEqual(ImportacionAcademica.objects.count(), 0)

    def test_rechaza_duplicar_carrera_con_tildes_y_mayusculas_distintas(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {
            'accion': 'previsualizar', 'tipo': 'oferta', 'anio': '2026', 'semestre': '2',
            'archivo': SimpleUploadedFile('oferta.csv', OFERTA, content_type='text/csv'),
        })
        fuente = 'Ingeniería en Informática'
        clave = hashlib.sha256(fuente.encode()).hexdigest()[:16]
        response = self.client.post(self.url, {
            'accion': 'aplicar', 'confirmado': 'si',
            'map_' + clave: '__crear__',
            'nuevo_nombre_' + clave: 'INGENIERIA EN INFORMATICA',
            'nueva_escuela_' + clave: 'Informática',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ya existe en EduNova')
        self.assertEqual(Carrera.objects.count(), 1)
        self.assertEqual(ImportacionAcademica.objects.count(), 0)

    def test_cancelar_vista_previa_no_crea_carrera(self):
        self.client.force_login(self.admin)
        fuente = 'Ecoturismo'
        oferta = OFERTA.replace('Ingeniería en Informática'.encode(), fuente.encode())
        self.client.post(self.url, {
            'accion': 'previsualizar', 'tipo': 'oferta', 'anio': '2026', 'semestre': '2',
            'archivo': SimpleUploadedFile('oferta.csv', oferta, content_type='text/csv'),
        })
        response = self.client.post(self.url, {'accion': 'cancelar'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Carrera.objects.filter(nombre=fuente).exists())

    def test_rollback_si_falla_importacion_tras_crear_carrera(self):
        from unittest.mock import patch
        from django.core.exceptions import ValidationError
        self.client.force_login(self.admin)
        fuente = 'Ecoturismo'
        oferta = OFERTA.replace('Ingeniería en Informática'.encode(), fuente.encode())
        self.client.post(self.url, {
            'accion': 'previsualizar', 'tipo': 'oferta', 'anio': '2026', 'semestre': '2',
            'archivo': SimpleUploadedFile('oferta.csv', oferta, content_type='text/csv'),
        })
        clave = hashlib.sha256(fuente.encode()).hexdigest()[:16]
        with patch('academico.importacion_vistas.aplicar_oferta', side_effect=ValidationError('Error simulado')):
            response = self.client.post(self.url, {
                'accion': 'aplicar', 'confirmado': 'si',
                'map_' + clave: '__crear__',
                'nuevo_nombre_' + clave: fuente,
                'nueva_escuela_' + clave: 'Turismo y Hospitalidad',
            })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Carrera.objects.filter(nombre=fuente).exists())
        self.assertEqual(ImportacionAcademica.objects.count(), 0)
