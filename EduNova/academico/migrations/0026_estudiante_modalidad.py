"""Modalidad del estudiante: diurno o vespertino. Conserva perfiles existentes."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('academico', '0025_importacion_academica_privada')]

    operations = [
        migrations.AddField(
            model_name='estudiante', name='modalidad',
            field=models.CharField(
                verbose_name='Modalidad de estudio', max_length=12,
                choices=[('diurno', 'Diurno'), ('vespertino', 'Vespertino')],
                blank=True, default='',
                help_text='Se define durante el registro. Los estudiantes antiguos pueden tenerla pendiente.',
            ),
        ),
    ]
