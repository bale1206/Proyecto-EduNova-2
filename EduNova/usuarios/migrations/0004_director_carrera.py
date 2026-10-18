from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [ ('usuarios','0003_curso_estudiante'), ('academico','0011_asignaturas_catalogo') ]
    operations = [migrations.AddField(model_name='usuario',name='carrera_dirigida',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='directores',to='academico.carrera',verbose_name='Carrera dirigida',help_text='Solo para directores de carrera; una carrera por director.'))]
