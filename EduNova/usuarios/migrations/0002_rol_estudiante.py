from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0001_initial')]
    operations = [migrations.AlterField(model_name='usuario', name='rol', field=models.CharField(max_length=30, choices=[('docente','Docente'),('estudiante','Estudiante'),('administrativo','Administrativo'),('administrador','Administrador')]))]
