from django.db import migrations


def comprobar_tablas_sin_datos(apps, schema_editor):
    """Evita eliminar accidentalmente información creada después de la auditoría."""
    for nombre in ('JustificacionRetiro', 'Observacion', 'Asistencia'):
        modelo = apps.get_model('academico', nombre)
        cantidad = modelo.objects.using(schema_editor.connection.alias).count()
        if cantidad:
            raise RuntimeError(
                f'No se elimina {nombre}: ahora tiene {cantidad} registro(s). '                 'Realiza respaldo y revisa la limpieza antes de continuar.'
            )


class Migration(migrations.Migration):
    dependencies = [
        ('academico', '0021_registro_guiado_estudiante'),
    ]

    operations = [
        migrations.RunPython(comprobar_tablas_sin_datos, migrations.RunPython.noop),
        migrations.DeleteModel(name='PermisoTablaCSV'),
        migrations.DeleteModel(name='JustificacionRetiro'),
        migrations.DeleteModel(name='Observacion'),
        migrations.DeleteModel(name='Asistencia'),
    ]
