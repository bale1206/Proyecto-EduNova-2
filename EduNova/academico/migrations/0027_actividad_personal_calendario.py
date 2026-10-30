"""Actividades privadas del calendario estudiantil sin modificar tareas existentes."""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('academico', '0026_estudiante_modalidad')]
    operations = [
        migrations.AddField(
            model_name='tareaestudio', name='tipo_actividad',
            field=models.CharField(
                max_length=12, default='tarea',
                choices=[('tarea','Tarea'), ('evaluacion','Evaluación'),
                         ('reunion','Reunión'), ('evento','Evento')],
            ),
        ),
    ]
