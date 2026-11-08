"""Alinea la columna física de apellido con el modelo sin perder datos.

Motivo: algunas bases Supabase ya tenían la columna "apellido" cambiada
manualmente, pero el código y las migraciones anteriores esperan "apellidos".
La migración es segura en ambos estados; no borra ni reescribe filas.
"""
from django.db import migrations, models


def _rename_if_needed(apps, schema_editor, source, target):
    Usuario = apps.get_model("usuarios", "Usuario")
    table = Usuario._meta.db_table
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        columns = {col.name for col in conn.introspection.get_table_description(cursor, table)}

    if source in columns and target in columns:
        raise RuntimeError(
            f"La tabla {table} tiene ambas columnas ({source}, {target}); "
            "requiere revisión manual para evitar perder información."
        )
    if target in columns:
        return  # La base ya está alineada, como en el Supabase reportado.
    if source not in columns:
        raise RuntimeError(
            f"No se encontró la columna {source} ni {target} en {table}. "
            "Detenga la migración y revise el esquema antes de continuar."
        )
    quote = schema_editor.quote_name
    schema_editor.execute(
        f"ALTER TABLE {quote(table)} "
        f"RENAME COLUMN {quote(source)} TO {quote(target)}"
    )


def forwards(apps, schema_editor):
    _rename_if_needed(apps, schema_editor, "apellidos", "apellido")


def backwards(apps, schema_editor):
    _rename_if_needed(apps, schema_editor, "apellido", "apellidos")


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0013_activar_cuentas_con_correo_verificado")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(forwards, backwards)],
            state_operations=[
                migrations.AlterField(
                    model_name="usuario",
                    name="apellidos",
                    field=models.CharField(
                        "Apellido", max_length=50, db_column="apellido"
                    ),
                ),
            ],
        ),
    ]
