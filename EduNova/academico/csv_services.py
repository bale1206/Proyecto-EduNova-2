"""CSV de tablas de negocio: nombres físicos de columnas y valores sin transformar."""
import csv
import io

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import AutoField, BooleanField
from django.http import HttpResponse

from .models import PermisoTablaCSV

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
NULL = r'\N'


class ErrorCSV(ValueError):
    pass


def tablas_disponibles():
    # Lista cerrada por aplicación. Nunca se acepta un nombre SQL del cliente.
    return {
        model._meta.db_table: model
        for label in ('academico', 'comunicacion')
        for model in apps.get_app_config(label).get_models(include_auto_created=True)
        if model is not PermisoTablaCSV and not model._meta.proxy and model._meta.managed
    }


def campos_tabla(model):
    """Respeta también el orden físico resultante de las migraciones de FK."""
    mapping = {field.column: field for field in model._meta.local_concrete_fields}
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, model._meta.db_table)
    columns = [column.name for column in description]
    if set(columns) != set(mapping):
        raise ErrorCSV('La estructura de la base de datos no coincide con el modelo; revisa las migraciones.')
    return [mapping[column] for column in columns]


def esquema(model):
    return [
        {
            'columna': f.column,
            'tipo': f.get_internal_type(),
            'nulo': f.null,
            'referencia': f.related_model._meta.db_table if f.is_relation else '',
        }
        for f in campos_tabla(model)
    ]


def _serializar(value):
    if value is None:
        return NULL
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value).replace('\\', '\\\\')


def respuesta_csv(model, plantilla=False):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    table = model._meta.db_table
    suffix = '_plantilla' if plantilla else ''
    response['Content-Disposition'] = f'attachment; filename="{table}{suffix}.csv"'
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response.write('\ufeff')
    writer = csv.writer(response)
    fields = campos_tabla(model)
    writer.writerow([f.column for f in fields])
    if not plantilla:
        rows = model._default_manager.order_by(model._meta.pk.attname).values_list(
            *[f.attname for f in fields]
        ).iterator(chunk_size=1000)
        for row in rows:
            writer.writerow([_serializar(value) for value in row])
    return response


def _convertir(field, cell):
    if cell == NULL:
        if not field.null:
            raise ErrorCSV(f'{field.column}: no admite NULL (\\N).')
        return None
    if cell == '' and isinstance(field, AutoField):
        return None  # ID automático al añadir registros nuevos.
    value = cell.replace('\\\\', '\\')
    target = field.target_field if field.is_relation else field
    if isinstance(target, BooleanField):
        if value.lower() in ('true', '1'):
            return True
        if value.lower() in ('false', '0'):
            return False
        raise ErrorCSV(f'{field.column}: usa true/false o 1/0; para NULL usa \\N.')
    try:
        return target.to_python(value)
    except (ValidationError, ValueError, TypeError) as exc:
        raise ErrorCSV(f'{field.column}: valor inválido para {target.get_internal_type()}.') from exc


def leer_csv(model, archivo):
    if not archivo.name.lower().endswith('.csv'):
        raise ErrorCSV('Selecciona un archivo con extensión .csv.')
    if archivo.size > MAX_BYTES:
        raise ErrorCSV('El archivo supera el máximo de 5 MB.')
    try:
        raw = archivo.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ErrorCSV('El archivo supera el máximo de 5 MB.')
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ErrorCSV('El archivo debe estar codificado en UTF-8.') from exc
    if '\x00' in content:
        raise ErrorCSV('El archivo contiene caracteres NUL inválidos.')
    fields = campos_tabla(model)
    expected = [f.column for f in fields]
    # Se acepta coma o punto y coma sin adivinar tipos ni modificar el encabezado.
    reader = None
    for delimiter in (',', ';'):
        candidate = csv.reader(io.StringIO(content, newline=''), delimiter=delimiter, strict=True)
        try:
            header = next(candidate, None)
        except csv.Error as exc:
            raise ErrorCSV('El encabezado CSV está mal formado.') from exc
        if header == expected:
            reader = candidate
            break
    if reader is None:
        raise ErrorCSV('Las columnas y su orden deben ser exactamente: ' + ', '.join(expected))
    rows = []
    try:
        for number, cells in enumerate(reader, start=2):
            if len(rows) >= MAX_ROWS:
                raise ErrorCSV('El archivo supera el máximo de 10.000 registros.')
            if len(cells) != len(fields):
                raise ErrorCSV(f'Fila {number}: se esperaban {len(fields)} columnas y llegaron {len(cells)}.')
            try:
                values = {f.attname: _convertir(f, cell) for f, cell in zip(fields, cells)}
            except ErrorCSV as exc:
                raise ErrorCSV(f'Fila {number}: {exc}') from exc
            rows.append((number, values))
    except csv.Error as exc:
        raise ErrorCSV(f'CSV mal formado cerca de la línea {reader.line_num}: {exc}') from exc
    if not rows:
        raise ErrorCSV('El archivo no contiene registros para importar.')
    return rows


def cargar_csv(model, archivo, permiso_pk):
    rows = leer_csv(model, archivo)
    with transaction.atomic():
        # Recomprueba la autorización y bloquea su modificación durante la carga.
        permiso = PermisoTablaCSV.objects.select_for_update().get(pk=permiso_pk)
        if not permiso.importar or permiso.tabla != model._meta.db_table:
            raise ErrorCSV('El director retiró el permiso de importación para esta tabla.')
        for number, values in rows:
            record = model(**values)
            try:
                if record.pk is not None and model._default_manager.filter(pk=record.pk).exists():
                    raise ErrorCSV(f'Fila {number}: el ID {record.pk} ya existe; no se sobrescriben registros.')
                exclude = [
                    f.name for f in model._meta.local_concrete_fields
                    if (values[f.attname] is None and (f.null or isinstance(f, AutoField)))
                ]
                record.full_clean(exclude=exclude)
                # Como al cargar fixtures: conserva fechas e IDs del CSV y no
                # ejecuta autocompletados de save() que cambiarían los datos.
                record.save_base(raw=True, force_insert=True)
            except ValidationError as exc:
                raise ErrorCSV(f'Fila {number}: ' + '; '.join(exc.messages)) from exc
            except IntegrityError as exc:
                raise ErrorCSV(f'Fila {number}: viola una restricción de la tabla (duplicado o referencia inválida).') from exc
    return len(rows)
