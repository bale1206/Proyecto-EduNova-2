import django.db.models.deletion
from django.db import migrations, models


def copiar_carreras_principales(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    through = Usuario.carreras_dirigidas.through
    alias = schema_editor.connection.alias
    for usuario in Usuario.objects.using(alias).filter(rol='administrativo', carrera_dirigida_id__isnull=False).iterator():
        through.objects.using(alias).get_or_create(usuario_id=usuario.pk, carrera_id=usuario.carrera_dirigida_id)


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0008_alter_usuario_curso'),
        ('academico', '0022_limpieza_modelo_escolar'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='carreras_dirigidas',
            field=models.ManyToManyField(
                blank=True, help_text='Todas las carreras del director de carrera.',
                related_name='directores_asignados', to='academico.carrera',
                verbose_name='Carreras dirigidas',
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='carreras_docencia',
            field=models.ManyToManyField(blank=True, related_name='docentes_registrados',
                to='academico.carrera', verbose_name='Carreras donde imparte clases'),
        ),
        migrations.RunPython(copiar_carreras_principales, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='usuario',
            name='carrera_dirigida',
            field=models.ForeignKey(
                blank=True, help_text='Carrera principal (compatibilidad con el panel actual).',
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='directores', to='academico.carrera',
                verbose_name='Carrera dirigida',
            ),
        ),
    ]
