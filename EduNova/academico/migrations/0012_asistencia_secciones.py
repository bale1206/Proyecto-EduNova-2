from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('academico', '0011_asignaturas_catalogo'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='SesionClase', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('fecha', models.DateField()), ('actualizada_en', models.DateTimeField(auto_now=True)),
            ('seccion', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sesiones_clase', to='academico.curso')),
            ('docente', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sesiones_clase', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-fecha']}),
        migrations.CreateModel(name='MarcaAsistencia', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('presente', models.BooleanField()), ('actualizado_en', models.DateTimeField(auto_now=True)),
            ('sesion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='marcas', to='academico.sesionclase')),
            ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='marcas_asistencia', to='academico.estudiante')),
        ]),
        migrations.CreateModel(name='AvisoAsistencia', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('texto', models.CharField(max_length=250)), ('creado_en', models.DateTimeField(auto_now_add=True)),
            ('leido', models.BooleanField(default=False)),
            ('destinatario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='avisos_asistencia', to=settings.AUTH_USER_MODEL)),
            ('marca', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='avisos', to='academico.marcaasistencia')),
        ], options={'ordering': ['-creado_en']}),
        migrations.AddConstraint(model_name='sesionclase', constraint=models.UniqueConstraint(fields=('seccion', 'fecha'), name='uq_sesion_seccion_fecha')),
        migrations.AddConstraint(model_name='marcaasistencia', constraint=models.UniqueConstraint(fields=('sesion', 'estudiante'), name='uq_marca_sesion_estudiante')),
    ]
