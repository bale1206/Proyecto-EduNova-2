from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from academico.horario_personal import COLUMNAS, leer_horario, clases_personales_por_dia
from academico.exportacion_horario import generar_horario_xlsx
from academico.models import BloqueHorarioPersonal, Carrera, TareaEstudio, Evento
from usuarios.models import Usuario

FILA = ['Programación', 'Lunes', '08:30', '09:50', '2026-11-01', '2026-11-30', 'Sala 2', 'Docente Uno']


def xlsx(filas=None, *, formula=False, hoja='Horario'):
    """Libro OOXML mínimo para probar datos externos sin depender de Excel."""
    filas = [COLUMNAS] + (filas if filas is not None else [FILA])
    rows = []
    for n, fila in enumerate(filas, 1):
        cells = []
        for i, valor in enumerate(fila):
            ref = f'{chr(65+i)}{n}'
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(valor))}</t></is></c>')
        if formula and n == 2:
            cells.append('<c r="I2"><f>1+1</f><v>2</v></c>')
        rows.append(f'<row r="{n}">{"".join(cells)}</row>')
    main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    stream = BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as z:
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets><sheet name="{hoja}" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{main}"><sheetData>{"".join(rows)}</sheetData></worksheet>')
    return stream.getvalue()


class LecturaHorarioTests(SimpleTestCase):
    def test_horario_valido(self):
        b = leer_horario(xlsx(), 'horario.xlsx')[0]
        self.assertEqual((b['dia_semana'], b['hora_inicio']), (1, '08:30:00'))

    def test_fechas_y_horas_numericas_excel(self):
        fila = FILA.copy()
        fila[2:6] = [510/1440, 590/1440, 46327, 46356]
        b = leer_horario(xlsx([fila]), 'horario.xlsx')[0]
        self.assertEqual(b['hora_inicio'], '08:30:00')

    def test_rechaza_formatos_y_libros_invalidos(self):
        for datos, nombre in [(b'no es excel', 'test.xlsx'), (xlsx(), 'test.csv'), (xlsx(hoja='Otra'), 'test.xlsx'), (xlsx([]), 'test.xlsx'), (xlsx(formula=True), 'test.xlsx')]:
            with self.subTest(nombre=nombre, datos=datos[:10]), self.assertRaises(ValueError):
                leer_horario(datos, nombre)

    def test_rechaza_cada_campo_invalido(self):
        for columna, valor in [(0, ''), (1, 'Otro'), (2, '25:00'), (3, '08:00'), (4, '01/11/2026'), (5, '2026-10-01'), (6, 'X'*101), (7, 'X'*151)]:
            fila = FILA.copy()
            fila[columna] = valor
            with self.subTest(columna=columna), self.assertRaises(ValueError):
                leer_horario(xlsx([fila]), 'horario.xlsx')

    def test_rechaza_duplicados_y_cruces(self):
        otra = FILA.copy()
        otra[2:4] = ['09:00', '10:30']
        for filas in ([FILA, FILA], [FILA, otra]):
            with self.assertRaisesMessage(ValueError, 'cruce'):
                leer_horario(xlsx(filas), 'horario.xlsx')

    def test_acepta_bloques_contiguos_y_periodos_disjuntos(self):
        otra = FILA.copy()
        otra[2:4] = ['09:50', '10:30']
        self.assertEqual(len(leer_horario(xlsx([FILA, otra]), 'test.xlsx')), 2)
        otra = FILA.copy()
        otra[4:6] = ['2026-12-01', '2026-12-31']
        self.assertEqual(len(leer_horario(xlsx([FILA, otra]), 'test.xlsx')), 2)

    def test_plantilla_real_vacia_y_ejemplo_compatible(self):
        datos = (Path(settings.BASE_DIR) / 'plantillas/horario-edunova.xlsx').read_bytes()
        with self.assertRaisesMessage(ValueError, 'Completa entre'):
            leer_horario(datos, 'horario.xlsx')
        stream = BytesIO()
        with ZipFile(BytesIO(datos)) as original, ZipFile(stream, 'w') as nuevo:
            for info in original.infolist():
                content = original.read(info.filename)
                if info.filename == 'xl/workbook.xml':
                    content = content.replace(b'name="Horario"', b'name="Vacio"').replace(b'name="Ejemplo"', b'name="Horario"')
                nuevo.writestr(info.filename, content)
        self.assertEqual(len(leer_horario(stream.getvalue(), 'horario.xlsx')), 3)


class ImportarHorarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alumno = Usuario.objects.create_user('12345678-5', 'a@duocuc.cl', 'ClaveSegura123!', rol='estudiante', first_name='Alumno', apellidos='Uno')
        cls.docente = Usuario.objects.create_user('9876543-3', 'd@profesor.duoc.cl', 'ClaveSegura123!', rol='docente', first_name='Docente', apellidos='Uno')
        cls.director = Usuario.objects.create_user('11111111-1', 'dir@duoc.cl', 'ClaveSegura123!', rol='administrativo', first_name='Director', apellidos='Uno')

    def cargar(self, filas=None):
        return self.client.post(reverse('academico:importar_horario'), {
            'archivo': SimpleUploadedFile('horario.xlsx', xlsx(filas)), 'accion': 'previsualizar'})

    def aplicar(self):
        return self.client.post(reverse('academico:importar_horario'), {'accion': 'aplicar', 'confirmar': 'si'})

    def test_solo_estudiantes_y_docentes(self):
        self.assertEqual(self.client.get(reverse('academico:importar_horario')).status_code, 302)
        self.client.force_login(self.director)
        for nombre in ('importar_horario', 'plantilla_horario'):
            self.assertEqual(self.client.get(reverse('academico:' + nombre)).status_code, 403)
        for usuario in (self.alumno, self.docente):
            self.client.force_login(usuario)
            response = self.client.get(reverse('academico:plantilla_horario'))
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_preview_no_escribe_y_confirmacion_muestra_calendario(self):
        for usuario, portal in ((self.alumno, 'home_estudiante'), (self.docente, 'home_docente')):
            self.client.force_login(usuario)
            self.assertContains(self.cargar(), 'Programación')
            self.assertFalse(usuario.bloques_horario.exists())
            self.assertRedirects(self.aplicar(), reverse('academico:' + portal) + '?year=2026&month=11')
            response = self.client.get(reverse('academico:' + portal), {'year': 2026, 'month': 11})
            self.assertContains(response, '08:30–09:50')
            self.assertContains(response, 'Programación')
            for nombre in ('name="seccion"', 'name="carrera"', 'filtro-seccion', 'filtro-carrera'):
                self.assertNotContains(response, nombre)
            calendario = clases_personales_por_dia(usuario, 2026, 11)
            self.assertEqual(set(calendario), {2, 9, 16, 23, 30})
            self.assertFalse(clases_personales_por_dia(usuario, 2026, 12))
            partial = self.client.get(reverse('academico:' + portal), {'year':2026, 'month':11}, HTTP_HX_REQUEST='true')
            self.assertContains(partial, '08:30–09:50')
            self.assertNotContains(partial, '<html')

    def test_confirmacion_obligatoria_y_cancelar(self):
        self.client.force_login(self.alumno)
        self.cargar()
        response = self.client.post(reverse('academico:importar_horario'), {'accion':'aplicar'})
        self.assertContains(response, 'Confirma que deseas')
        self.assertFalse(self.alumno.bloques_horario.exists())
        self.client.post(reverse('academico:importar_horario'), {'accion':'cancelar'})
        self.assertContains(self.aplicar(), 'Carga primero')

    def test_reemplaza_solo_propio_horario_y_conserva_tareas(self):
        for usuario in (self.alumno, self.docente):
            self.client.force_login(usuario)
            self.cargar()
            self.aplicar()
        tarea = TareaEstudio.objects.create(estudiante=self.alumno, titulo='Conservar')
        self.client.force_login(self.alumno)
        nueva = FILA.copy()
        nueva[0] = 'Matemática'
        self.cargar([nueva])
        self.aplicar()
        self.assertEqual(list(self.alumno.bloques_horario.values_list('asignatura', flat=True)), ['Matemática'])
        self.assertEqual(self.docente.bloques_horario.get().asignatura, 'Programación')
        self.assertTrue(TareaEstudio.objects.filter(pk=tarea.pk).exists())

    def test_archivo_invalido_no_altera_horario(self):
        self.client.force_login(self.alumno)
        self.cargar()
        self.aplicar()
        self.assertContains(self.cargar([FILA, FILA]), 'cruce')
        self.assertEqual(self.alumno.bloques_horario.count(), 1)
        self.assertContains(self.aplicar(), 'Carga primero')

    def test_fallo_de_escritura_revierte_reemplazo(self):
        self.client.force_login(self.alumno)
        self.cargar()
        self.aplicar()
        self.cargar()
        with patch('academico.horario_vistas.BloqueHorarioPersonal.objects.bulk_create', side_effect=RuntimeError('simulado')):
            with self.assertRaises(RuntimeError):
                self.aplicar()
        self.assertEqual(self.alumno.bloques_horario.count(), 1)

    def test_estudiante_crea_actividad_sin_asignatura(self):
        self.client.force_login(self.alumno)
        response = self.client.post(reverse('academico:crear_tarea_estudiante'), {
            'titulo':'Estudiar', 'fecha_limite':'2026-11-12', 'hora_inicio':'18:00', 'tipo_actividad':'tarea'})
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.alumno.tareas_estudio.get().seccion_id)

    def test_director_y_docente_crean_eventos_sin_catalogos(self):
        for usuario, portal in ((self.director, 'home_administrativo'), (self.docente, 'home_docente')):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse('academico:' + portal)).status_code, 200)
            self.client.post(reverse('academico:crear_evento'), {
                'tipo':'reunion', 'titulo':'Reunión privada', 'fecha':'2026-11-12', 'hora_inicio':'09:00', 'hora_fin':'10:00'})
            ev = Evento.objects.get(creado_por=usuario)
            self.assertIsNone(ev.carrera_id)
            self.assertIsNone(ev.curso_id)
        self.client.force_login(self.alumno)
        self.assertNotContains(self.client.get(reverse('academico:home_estudiante'), {'year':2026, 'month':11}), 'Reunión privada')

    def test_exportacion_es_privada_y_reimportable(self):
        self.client.force_login(self.alumno)
        self.cargar()
        self.aplicar()
        self.client.force_login(self.docente)
        otra = FILA.copy()
        otra[0] = 'Asignatura secreta docente'
        self.cargar([otra])
        self.aplicar()
        self.client.force_login(self.alumno)
        respuesta = self.client.get(reverse('academico:exportar_horario'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Cache-Control'], 'private, no-store')
        self.assertIn('mi-horario-edunova.xlsx', respuesta['Content-Disposition'])
        datos = respuesta.content
        self.assertTrue(datos.startswith(b'PK'))
        self.assertNotIn(b'Asignatura secreta docente', datos)
        bloques = leer_horario(datos, 'mi-horario-edunova.xlsx')
        self.assertEqual(len(bloques), 1)
        self.assertEqual(bloques[0]['asignatura'], 'Programación')
        self.assertEqual(bloques[0]['dia_semana'], 1)
        self.assertEqual(bloques[0]['hora_inicio'], '08:30:00')
        self.assertContains(self.client.get(reverse('academico:importar_horario')),
                            'Cómo completar tu horario: paso a paso')
        self.assertContains(self.client.get(reverse('academico:home_estudiante')),
                            'Exportar mi horario XLSX')
        # El archivo exportado funciona como entrada del flujo de importación.
        revisado = self.client.post(reverse('academico:importar_horario'), {
            'archivo': SimpleUploadedFile('mi-horario-edunova.xlsx', datos),
            'accion': 'previsualizar',
        })
        self.assertContains(revisado, 'Programación')
        self.assertRedirects(self.aplicar(),
                             reverse('academico:home_estudiante') + '?year=2026&month=11')

    def test_exportacion_permisos_y_horario_vacio(self):
        ruta = reverse('academico:exportar_horario')
        self.assertEqual(self.client.get(ruta).status_code, 302)
        self.client.force_login(self.director)
        self.assertEqual(self.client.get(ruta).status_code, 403)
        for usuario in (self.alumno, self.docente):
            self.client.force_login(usuario)
            respuesta = self.client.get(ruta)
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.content.startswith(b'PK'))
            with self.assertRaisesMessage(ValueError, 'Completa entre'):
                leer_horario(respuesta.content, 'mi-horario-edunova.xlsx')
            self.assertContains(self.client.get(reverse('academico:importar_horario')),
                                'Fecha inicio')
            self.assertContains(self.client.get(reverse('academico:home_docente'
                if usuario.rol == 'docente' else 'academico:home_estudiante')),
                'Exportar mi horario XLSX')

    def test_querystring_antigua_no_filtra_ni_consulta_catalogos(self):
        Carrera.objects.create(nombre='Carrera histórica', escuela='Escuela')
        self.client.force_login(self.alumno)
        response = self.client.get(reverse('academico:home_estudiante'), {'carrera':'ajena', 'seccion':'ajena'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Carrera histórica')
        self.assertTrue(Carrera.objects.filter(nombre='Carrera histórica').exists())
