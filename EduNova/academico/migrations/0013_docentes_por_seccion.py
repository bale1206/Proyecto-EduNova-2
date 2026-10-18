from django.conf import settings
from django.db import migrations, models


def copiar_docentes(apps, schema_editor):
    Seccion = apps.get_model('academico', 'Curso')
    db = schema_editor.connection.alias
    for seccion in Seccion.objects.using(db).exclude(docente_jefe_id__isnull=True).iterator():
        seccion.docentes.add(seccion.docente_jefe_id)


class Migration(migrations.Migration):
    dependencies = [
        ('academico', '0012_asistencia_secciones'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name='curso', name='docentes',
            field=models.ManyToManyField(
                blank=True, limit_choices_to={'rol': 'docente'},
                related_name='secciones_impartidas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Docentes asignados',
            ),
        ),
        migrations.RunPython(copiar_docentes, migrations.RunPython.noop),
        migrations.AlterModelOptions(name='curso', options={
            'verbose_name': 'Sección de asignatura',
            'verbose_name_plural': 'Secciones de asignaturas',
            'ordering': ['seccion'],
        }),
    ]
