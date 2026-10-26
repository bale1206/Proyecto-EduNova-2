from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('academico','0017_avance_estudiante_csv'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='tareaestudio', name='seccion', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tareas_estudiantes', to='academico.curso', verbose_name='Asignatura y sección')),
        migrations.AddField(model_name='tareaestudio', name='color', field=models.CharField(default='#4C849D', max_length=7)),
        migrations.AddField(model_name='tareaestudio', name='prioridad', field=models.CharField(choices=[('alta','Alta'),('media','Media'),('baja','Baja')], default='media', max_length=5)),
        migrations.AddField(model_name='tareaestudio', name='frecuencia', field=models.CharField(choices=[('ninguna','Sin avisos'),('una','24 horas antes'),('diaria','Diariamente desde tres días antes'),('dos','Tres días y un día antes')],default='ninguna',max_length=8)),
        migrations.AddField(model_name='tareaestudio', name='canal', field=models.CharField(choices=[('interno','Campana'),('push','Celular'),('ambos','Ambos')],default='interno',max_length=8)),
        migrations.CreateModel(name='RecordatorioTarea', fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('programado_para',models.DateTimeField()),('texto',models.CharField(max_length=300)),('leido',models.BooleanField(default=False)),('enviado_push',models.BooleanField(default=False)),('creado_en',models.DateTimeField(auto_now_add=True)),('estudiante',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='recordatorios_tareas',to=settings.AUTH_USER_MODEL)),('tarea',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='recordatorios',to='academico.tareaestudio'))], options={'ordering':['-creado_en']}),
        migrations.CreateModel(name='SuscripcionPush', fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('endpoint',models.TextField(unique=True)),('p256dh',models.TextField()),('auth',models.TextField()),('creada_en',models.DateTimeField(auto_now_add=True)),('usuario',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='suscripciones_push',to=settings.AUTH_USER_MODEL))]),
        migrations.AddConstraint(model_name='recordatoriotarea', constraint=models.UniqueConstraint(fields=['tarea','programado_para'],name='uq_recordatorio_tarea_fecha')),
    ]
