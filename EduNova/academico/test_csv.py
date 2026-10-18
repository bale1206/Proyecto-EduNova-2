import csv
import io
from datetime import datetime, timezone

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from .csv_services import ErrorCSV, cargar_csv, campos_tabla, respuesta_csv, tablas_disponibles
from .models import Curso, Estudiante, Observacion, ObservacionComportamiento, PermisoTablaCSV, RegistroAsistencia


def archivo(model, rows, header=None, delimiter=','):
    output = io.StringIO(newline='')
    writer = csv.writer(output, delimiter=delimiter)
    fields = model._meta.local_concrete_fields
    physical = campos_tabla(model)
    writer.writerow(header or [f.column for f in physical])
    for row in rows:
        if model is Curso and not header and len(row) == 3:
            values = dict(zip(['id', 'asignatura', 'docente_jefe_id'], row))
            values.update(turno=True, seccion='')
            row = [values.get(f.column, r'\N' if f.null else '') for f in fields]
        if model is RegistroAsistencia and not header and len(row) == 6:
            values = dict(zip(['id', 'estudiante_id', 'docente_id', 'presente', 'justificado', 'fecha'], row))
            row = [values.get(f.column, r'\N' if f.null else '') for f in fields]
        if not header and len(row) == len(fields):
            values = dict(zip([f.column for f in fields], row))
            row = [values[f.column] for f in physical]
        writer.writerow(row)
    return SimpleUploadedFile('datos.csv', output.getvalue().encode('utf-8-sig'), content_type='text/csv')


class CSVTests(TestCase):
    def setUp(self):
        self.administrativo = Usuario.objects.create_user(rut='1-9', rol='administrativo')
        self.otro_administrativo = Usuario.objects.create_user(rut='2-7', rol='administrativo')
        self.administrador = Usuario.objects.create_superuser(rut='9-1', email='admin@example.com', password='test-pass')
        self.docente = Usuario.objects.create_user(rut='3-5', rol='docente')
        self.apoderado = Usuario.objects.create_user(rut='4-3', rol='apoderado')
        self.permiso = PermisoTablaCSV.objects.create(tabla=Curso._meta.db_table, exportar=True, importar=True)

    def cargar(self, model, rows, **kwargs):
        permiso, _ = PermisoTablaCSV.objects.get_or_create(tabla=model._meta.db_table, defaults={'importar': True})
        return cargar_csv(model, archivo(model, rows, **kwargs), permiso.pk)

    def test_administrativos_configuran_y_docente_no_puede_configurar(self):
        self.client.force_login(self.docente)
        self.assertEqual(self.client.post(reverse('academico:configurar_csv')).status_code, 403)
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.get(reverse('academico:configurar_csv')).status_code, 200)
        self.client.post(reverse('academico:configurar_csv'), {'exportar': [Curso._meta.db_table]})
        self.permiso.refresh_from_db()
        self.assertTrue(self.permiso.exportar)
        self.assertFalse(self.permiso.importar)
        self.assertEqual(self.client.get(reverse('usuarios:post_login_redirect')).url, reverse('academico:home_administrativo'))
        self.client.force_login(self.otro_administrativo)
        self.assertContains(self.client.get(reverse('academico:configurar_csv')), 'checked')

    def test_exportacion_preserva_columnas_y_texto(self):
        course = Curso.objects.create(asignatura='Niñez, "A"\nSegunda línea \\N', docente_jefe=self.docente)
        self.client.force_login(self.administrativo)
        response = self.client.get(reverse('academico:exportar_csv', args=[self.permiso.tabla]))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0], [f.column for f in campos_tabla(Curso)])
        self.assertEqual(dict(zip(rows[0], rows[1]))['asignatura'], course.asignatura.replace('\\', '\\\\'))
        payload = response.content
        course.delete()
        self.assertEqual(cargar_csv(Curso, SimpleUploadedFile('datos.csv', payload), self.permiso.pk), 1)
        self.assertEqual(Curso.objects.get().asignatura, 'Niñez, "A"\nSegunda línea \\N')

    def test_ejemplo_de_cursos_es_independiente_de_datos_reales(self):
        Curso.objects.create(asignatura='Curso privado')
        self.client.force_login(self.administrativo)
        response = self.client.get(reverse('academico:ejemplo_csv', args=[Curso._meta.db_table]))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0], [f.column for f in campos_tabla(Curso)])
        self.assertEqual(len(rows), 3)
        self.assertNotIn('Curso privado', response.content.decode('utf-8-sig'))
        self.assertEqual(Curso.objects.count(), 1)

    def test_ejemplo_de_estudiantes_exige_permiso_de_importacion(self):
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.get(reverse('academico:ejemplo_csv', args=[Estudiante._meta.db_table])).status_code, 404)
        PermisoTablaCSV.objects.create(tabla=Estudiante._meta.db_table, importar=True)
        response = self.client.get(reverse('academico:ejemplo_csv', args=[Estudiante._meta.db_table]))
        self.assertContains(response, 'rut_estudiante')
        self.assertEqual(Estudiante.objects.count(), 0)

    def test_plantilla_no_expone_datos_con_permiso_solo_importar(self):
        Curso.objects.create(asignatura='Privado')
        self.permiso.exportar = False
        self.permiso.save()
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.get(reverse('academico:exportar_csv', args=[self.permiso.tabla])).status_code, 403)
        response = self.client.get(reverse('academico:plantilla_csv', args=[self.permiso.tabla]))
        self.assertEqual(list(csv.reader(io.StringIO(response.content.decode('utf-8-sig')))), [[f.column for f in campos_tabla(Curso)]])

    def test_roles_y_tablas_protegidas(self):
        self.assertNotIn('usuarios_usuario', tablas_disponibles())
        self.assertNotIn(PermisoTablaCSV._meta.db_table, tablas_disponibles())
        for user in (self.docente, self.apoderado, self.administrador):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('academico:exportar_csv', args=[self.permiso.tabla])).status_code, 403)
            self.assertEqual(self.client.get(reverse('academico:configurar_csv')).status_code, 403)
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.get(reverse('academico:exportar_csv', args=['usuarios_usuario'])).status_code, 403)
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.post(reverse('academico:configurar_csv'), {'exportar': ['usuarios_usuario']}).status_code, 403)

    def test_panel_y_carga_desde_formulario(self):
        self.client.force_login(self.administrativo)
        self.assertContains(self.client.get(reverse('academico:panel_csv')), 'academico_curso')
        self.assertContains(self.client.get(reverse('academico:home_administrativo')), 'Reportes e importación CSV')
        self.assertEqual(self.client.get(reverse('academico:importar_csv', args=[self.permiso.tabla])).status_code, 405)
        response = self.client.post(reverse('academico:importar_csv', args=[self.permiso.tabla]), {
            'archivo': archivo(Curso, [['', 'Nuevo', r'\N']])}, follow=True)
        self.assertContains(response, 'Se añadieron 1 registros')
        self.assertIsNone(Curso.objects.get().docente_jefe_id)
        self.permiso.importar = False
        self.permiso.save()
        self.assertEqual(self.client.post(reverse('academico:importar_csv', args=[self.permiso.tabla]), {
            'archivo': archivo(Curso, [['', 'Otro', r'\N']])}).status_code, 403)

    def test_estructura_exacta_y_filas_malformadas(self):
        for header in (['asignatura', 'id', 'docente_jefe_id'], ['id', 'asignatura'], ['id', 'asignatura', 'asignatura']):
            with self.assertRaisesRegex(ErrorCSV, 'columnas'):
                self.cargar(Curso, [['', 'Curso', r'\N']], header=header)
        with self.assertRaisesRegex(ErrorCSV, 'Fila 2'):
            self.cargar(Curso, [['', 'Curso']])
        self.assertEqual(Curso.objects.count(), 0)

    def test_validacion_y_reversion_total(self):
        for bad in (['', 'Curso', '99999'], ['', 'Curso', str(self.apoderado.pk)], ['', 'x' * 151, r'\N']):
            with self.assertRaisesRegex(ErrorCSV, 'Fila 3'):
                self.cargar(Curso, [['', 'Válido', r'\N'], bad])
            self.assertEqual(Curso.objects.count(), 0)

    def test_ids_duplicados_no_reemplazan_datos(self):
        course = Curso.objects.create(asignatura='Original')
        with self.assertRaisesRegex(ErrorCSV, 'ya existe'):
            self.cargar(Curso, [['', 'Nuevo', r'\N'], [course.pk, 'Reemplazo', r'\N']])
        self.assertEqual(list(Curso.objects.values_list('asignatura', flat=True)), ['Original'])
        with self.assertRaisesRegex(ErrorCSV, 'Fila 3'):
            self.cargar(Curso, [['500', 'Lenguaje', r'\N'], ['500', 'Historia', r'\N']])
        self.assertFalse(Curso.objects.filter(pk=500).exists())

    def test_punto_y_coma_y_revocacion(self):
        self.assertEqual(self.cargar(Curso, [['', 'Matemática', r'\N']], delimiter=';'), 1)
        self.permiso.importar = False
        self.permiso.save()
        with self.assertRaisesRegex(ErrorCSV, 'retiró'):
            cargar_csv(Curso, archivo(Curso, [['', 'Programación', r'\N']]), self.permiso.pk)
        self.assertEqual(Curso.objects.count(), 1)

    def test_utf8_tamano_y_csv_invalido(self):
        from unittest.mock import patch
        for upload in (SimpleUploadedFile('datos.csv', b'\xff'), SimpleUploadedFile('datos.txt', b'a'),
                       SimpleUploadedFile('datos.csv', b'id,asignatura,docente_jefe_id\n"incompleto')):
            with self.assertRaises(ErrorCSV):
                cargar_csv(Curso, upload, self.permiso.pk)
        with patch('academico.csv_services.MAX_BYTES', 2):
            with self.assertRaisesRegex(ErrorCSV, '5 MB'):
                self.cargar(Curso, [['', 'Curso', r'\N']])
        with patch('academico.csv_services.MAX_ROWS', 1):
            with self.assertRaisesRegex(ErrorCSV, '10.000'):
                self.cargar(Curso, [['', 'Curso', r'\N'], ['', 'Otro', r'\N']])

    def test_booleanos_y_fechas_automaticas_se_conservan(self):
        course = Curso.objects.create(asignatura='Matemática')
        student = Estudiante.objects.create(rut_estudiante='5-1', nombre_completo='Ana Pérez', curso=course, apoderado=self.apoderado)
        self.cargar(RegistroAsistencia, [['', student.pk, self.docente.pk, 'true', r'\N', '2020-01-02T10:30:00+00:00']])
        record = RegistroAsistencia.objects.get()
        self.assertTrue(record.presente)
        self.assertIsNone(record.justificado)
        self.assertEqual(record.fecha, datetime(2020, 1, 2, 10, 30, tzinfo=timezone.utc))
        with self.assertRaises(ErrorCSV):
            self.cargar(RegistroAsistencia, [['', student.pk, self.docente.pk, 'quizás', 'false', '2020-01-02T10:30:00+00:00']])
        self.cargar(Observacion, [['', student.pk, self.docente.pk, '2020-01-02', 'otra', 'Nota', 'false']])
        self.assertEqual(Observacion.objects.get().fecha.isoformat(), '2020-01-02')

    def test_tabla_intermedia_muchos_a_muchos(self):
        course = Curso.objects.create(asignatura='Matemática')
        student = Estudiante.objects.create(rut_estudiante='5-1', nombre_completo='Ana Pérez', curso=course, apoderado=self.apoderado)
        observation = ObservacionComportamiento.objects.create(docente=self.docente, asunto='Nota', tipo_observacion='SANCION', curso=course, descripcion='Texto')
        model = ObservacionComportamiento.estudiantes.through
        self.assertIn(model._meta.db_table, tablas_disponibles())
        self.cargar(model, [['', observation.pk, student.pk]])
        self.assertEqual(list(observation.estudiantes.all()), [student])
        with self.assertRaises(ErrorCSV):
            self.cargar(model, [['', observation.pk, student.pk]])
        self.assertEqual(model.objects.count(), 1)
