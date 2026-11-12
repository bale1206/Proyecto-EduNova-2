"""Lectura de documentos y regresiones de la retirada del importador del admin."""
from types import SimpleNamespace
from unittest import TestCase as PythonTestCase

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from django.urls import NoReverseMatch, resolve, reverse

from academico.importacion_archivos import leer_malla, leer_oferta

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


class ImportadorAdminEliminadoTests(SimpleTestCase):
    def test_rutas_del_importador_no_tienen_nombre_publico(self):
        for nombre, kwargs in (
            ('edunova_importaciones_admin', {}),
            ('edunova_importaciones_plantilla', {}),
            ('edunova_importaciones_archivo', {'pk': 1}),
        ):
            with self.subTest(nombre=nombre), self.assertRaises(NoReverseMatch):
                reverse(nombre, kwargs=kwargs)

    def test_antiguas_rutas_devuelven_404_para_administrador(self):
        for ruta in (
            '/admin/importaciones-academicas/',
            '/admin/importaciones-academicas/plantilla/',
            '/admin/importaciones-academicas/archivo/1/',
        ):
            for metodo in ('get', 'post'):
                with self.subTest(ruta=ruta, metodo=metodo):
                    request = getattr(RequestFactory(), metodo)(ruta)
                    request._dont_enforce_csrf_checks = True
                    request.user = SimpleNamespace(is_active=True, is_staff=True, is_superuser=True)
                    match = resolve(ruta)
                    with self.assertRaises(Http404):
                        match.func(request, *match.args, **match.kwargs)

