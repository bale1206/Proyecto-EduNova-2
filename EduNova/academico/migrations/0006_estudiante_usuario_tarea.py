from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('academico', '0005_permisotablacsv'), ('usuarios', '0002_rol_estudiante')]
    operations = [
        migrations.AddField(model_name='estudiante', name='usuario', field=models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='perfil_estudiante', limit_choices_to={'rol':'estudiante'}, verbose_name='Cuenta de estudiante')),
        migrations.CreateModel(name='TareaEstudio',fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
            ('titulo',models.CharField(max_length=160)),('descripcion',models.TextField(blank=True)),
            ('fecha_limite',models.DateField(null=True,blank=True)),('completada',models.BooleanField(default=False)),
            ('creada_en',models.DateTimeField(auto_now_add=True)),
            ('estudiante',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.CASCADE,related_name='tareas_estudio',limit_choices_to={'rol':'estudiante'})),
        ], options={'ordering':['completada','fecha_limite','-creada_en'],'verbose_name':'Tarea de estudio','verbose_name_plural':'Tareas de estudio'}),
    ]
