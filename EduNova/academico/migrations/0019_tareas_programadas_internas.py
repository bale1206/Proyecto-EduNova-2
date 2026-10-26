from django.db import migrations, models


def convertir_preferencias(apps, schema_editor):
    Tarea = apps.get_model('academico', 'TareaEstudio')
    # Los avisos antiguos pasan a ser internos; ninguno activa notificaciones al celular.
    Tarea.objects.exclude(frecuencia='ninguna').update(recordatorios_activos=True)


class Migration(migrations.Migration):
    dependencies = [('academico', '0018_planificador_recordatorios')]
    operations = [
        migrations.AddField('tareaestudio', 'hora_inicio', models.TimeField(null=True, blank=True, verbose_name='Hora de realización')),
        migrations.AddField('tareaestudio', 'repeticion', models.CharField(max_length=8, default='ninguna', choices=[('ninguna','No repetir'),('diaria','Cada día'),('semanal','Cada semana'),('mensual','Cada mes')])),
        migrations.AddField('tareaestudio', 'minutos_antes', models.PositiveSmallIntegerField(default=15, choices=[(0,'A la hora'),(5,'5 minutos antes'),(10,'10 minutos antes'),(15,'15 minutos antes'),(30,'30 minutos antes'),(60,'1 hora antes')])),
        migrations.AddField('tareaestudio', 'recordatorios_activos', models.BooleanField(default=False)),
        migrations.RunPython(convertir_preferencias, migrations.RunPython.noop),
        migrations.RemoveField('tareaestudio', 'frecuencia'),
        migrations.RemoveField('tareaestudio', 'canal'),
        migrations.RemoveField('recordatoriotarea', 'enviado_push'),
        migrations.DeleteModel('SuscripcionPush'),
    ]
