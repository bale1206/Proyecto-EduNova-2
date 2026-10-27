from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('academico', '0019_tareas_programadas_internas')]
    operations = [
        migrations.AddField(model_name='evento', name='carrera', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='eventos_planificacion', to='academico.carrera')),
        migrations.AlterField(model_name='evento', name='curso', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to='academico.curso')),
        migrations.AlterField(model_name='tareaestudio', name='estudiante', field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tareas_estudio', to='usuarios.usuario')),
    ]
