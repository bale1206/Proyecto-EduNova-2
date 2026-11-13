"""Regresiones de interfaces y plantillas XLSX por perfil.

Ejecutar con --settings=edunova_project.settings_test (base SQLite en memoria).
"""
from datetime import date, time
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, reverse

from academico.exportacion_horario import generar_horario_xlsx
from academico.horario_personal import COLUMNAS, COLUMNAS_ANTIGUAS, COLUMNAS_ESTUDIANTE, leer_horario
from academico.importacion_archivos import leer_xlsx
from academico.routing import websocket_urlpatterns
from usuarios.models import Usuario


class FormatoExcelSegunRolTests(SimpleTestCase):
    def test_plantillas_distintas_para_estudiante_y_docente(self):
        base = Path(settings.BASE_DIR) / 'plantillas'
        estudiante = (base / 'horario-edunova.xlsx').read_bytes()
        docente = (base / 'horario-edunova-docente.xlsx').read_bytes()
        self.assertTrue(estudiante.startswith(b'PK'))
        self.assertTrue(docente.startswith(b'PK'))
        self.assertEqual(tuple(leer_xlsx(estudiante, 'Horario')[0]), COLUMNAS_ESTUDIANTE)
        self.assertEqual(tuple(leer_xlsx(docente, 'Horario')[0]), COLUMNAS)
        self.assertEqual(len(leer_xlsx(estudiante, 'Horario')), 1)
        self.assertEqual(len(leer_xlsx(docente, 'Horario')), 1)
        ejemplos_estudiante = leer_xlsx(estudiante, 'Ejemplo')
        ejemplos_docente = leer_xlsx(docente, 'Ejemplo')
        self.assertEqual(tuple(ejemplos_estudiante[0]), COLUMNAS_ESTUDIANTE)
        self.assertEqual(tuple(ejemplos_docente[0]), COLUMNAS)
        self.assertEqual(len(ejemplos_estudiante), 4)
        self.assertEqual(len(ejemplos_docente), 4)
        self.assertEqual(ejemplos_estudiante[1][7], 'Profesora Ejemplo')
        self.assertNotIn('Docente', COLUMNAS)

    def test_exportaciones_segun_rol_se_pueden_reimportar(self):
        bloque = SimpleNamespace(
            asignatura='Programación', dia_semana=1, hora_inicio=time(8, 30),
            hora_fin=time(9, 50), fecha_inicio=date(2027, 3, 1),
            fecha_fin=date(2027, 7, 15), sala='Sala 204', docente='Profesora Referencia',
        )
        excel_estudiante = generar_horario_xlsx([bloque], incluir_docente=True)
        excel_docente = generar_horario_xlsx([bloque], incluir_docente=False)
        self.assertEqual(tuple(leer_xlsx(excel_estudiante, 'Horario')[0]), COLUMNAS_ESTUDIANTE)
        self.assertEqual(tuple(leer_xlsx(excel_docente, 'Horario')[0]), COLUMNAS)
        estudiante = leer_horario(excel_estudiante, 'estudiante.xlsx')
        docente = leer_horario(excel_docente, 'docente.xlsx')
        self.assertEqual(estudiante[0]['asignatura'], 'Programación')
        self.assertEqual(estudiante[0]['docente'], 'Profesora Referencia')
        self.assertEqual(docente[0]['asignatura'], 'Programación')
        self.assertEqual(docente[0]['docente'], '')

    def test_archivos_de_ocho_columnas_siguen_siendo_compatibles(self):
        # Los archivos antiguos aún pueden importarse, aunque ya no se muestran
        # ni se generan nuevas columnas de docente.
        from io import BytesIO
        from xml.sax.saxutils import escape
        from zipfile import ZIP_DEFLATED
        main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        filas = [COLUMNAS_ANTIGUAS,
                 ('Programación','Lunes','08:30','09:50','2027-03-01','2027-07-15','Sala 204','Profesor Antiguo')]
        rows = []
        for idx, fila in enumerate(filas, 1):
            cells = ''.join(f'<c r="{chr(65+j)}{idx}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
                            for j,v in enumerate(fila))
            rows.append(f'<row r="{idx}">{cells}</row>')
        stream = BytesIO()
        with ZipFile(stream, 'w', ZIP_DEFLATED) as book:
            book.writestr('xl/workbook.xml',
                f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets><sheet name="Horario" sheetId="1" r:id="r1"/></sheets></workbook>')
            book.writestr('xl/_rels/workbook.xml.rels',
                '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            book.writestr('xl/worksheets/sheet1.xml',
                f'<worksheet xmlns="{main}"><sheetData>{"".join(rows)}</sheetData></worksheet>')
        self.assertEqual(leer_horario(stream.getvalue(), 'antiguo.xlsx')[0]['docente'],
                         'Profesor Antiguo')


class InterfazSinAsistenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = Usuario.objects.create_user('12345678-5', 'alumno@duocuc.cl', 'ClaveSegura123!',
            rol='estudiante', first_name='Alumno', apellidos='Prueba')
        cls.docente = Usuario.objects.create_user('9876543-3', 'profesor@gmail.com', 'ClaveSegura123!',
            rol='docente', first_name='Docente', apellidos='Prueba')
        cls.director = Usuario.objects.create_user('11111111-1', 'director@gmail.com', 'ClaveSegura123!',
            rol='administrativo', first_name='Director', apellidos='Prueba')

    def test_calendarios_de_tres_perfiles_no_muestran_asistencia(self):
        for usuario, portal in (
            (self.estudiante, 'home_estudiante'),
            (self.docente, 'home_docente'),
            (self.director, 'home_administrativo'),
        ):
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                resp = self.client.get(reverse('academico:' + portal))
                self.assertEqual(resp.status_code, 200)
                for marcador in ('Avisos de asistencia','Mis avisos de asistencia',
                                 'Lista de Estudiantes','Registro de asistencia'):
                    self.assertNotContains(resp, marcador)
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('academico:home_estudiante'))
        self.assertNotContains(respuesta, '<h2 class="font-display font-semibold mb-3">Mi cuenta</h2>')
        self.assertNotContains(respuesta, 'Código EduNova:')

    def test_accesos_a_asistencia_fuera_de_los_portales(self):
        for nombre in ('tomar_asistencia', 'analitica_carrera'):
            with self.subTest(nombre=nombre), self.assertRaises(NoReverseMatch):
                reverse('academico:' + nombre)
        # El AJAX de estudiantes sigue activo por usarse en Observaciones.
        self.assertTrue(reverse('academico:ajax_cargar_estudiantes'))
        self.assertFalse(websocket_urlpatterns)

    def test_descarga_no_enciende_indicador_global(self):
        self.client.force_login(self.estudiante)
        for portal in ('home_estudiante','importar_horario'):
            resp = self.client.get(reverse('academico:' + portal))
            self.assertContains(resp, 'download="horario-edunova.xlsx"')
            self.assertContains(resp, 'download="mi-horario-edunova.xlsx"')

    def test_tablas_y_plantillas_tienen_columnas_segun_rol(self):
        for usuario, incluye_docente, nombre in (
            (self.estudiante, True, 'horario-edunova.xlsx'),
            (self.docente, False, 'horario-edunova-docente.xlsx'),
        ):
            with self.subTest(rol=usuario.rol):
                self.client.force_login(usuario)
                html = self.client.get(reverse('academico:importar_horario')).content.decode('utf-8')
                self.assertEqual('<th>Docente</th>' in html, incluye_docente)
                self.assertIn('Cómo completar tu horario', html)
                self.assertIn('download="' + nombre + '"', html)
                respuesta = self.client.get(reverse('academico:plantilla_horario'))
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(nombre, respuesta['Content-Disposition'])
                contenido = b''.join(respuesta.streaming_content)
                respuesta.close()
                columnas = COLUMNAS_ESTUDIANTE if incluye_docente else COLUMNAS
                self.assertEqual(tuple(leer_xlsx(contenido, 'Horario')[0]), columnas)
                descarga = self.client.get(reverse('academico:exportar_horario'))
                self.assertEqual(descarga.status_code, 200)
                self.assertEqual(tuple(leer_xlsx(descarga.content, 'Horario')[0]), columnas)
