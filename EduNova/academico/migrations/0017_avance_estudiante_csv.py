from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('academico', '0016_eliminar_secciones_conservar_historial')]
    operations = [
        migrations.AddField(model_name='estudiante', name='anio_carrera', field=models.PositiveSmallIntegerField(blank=True, choices=[(1, '1° año'), (2, '2° año'), (3, '3° año'), (4, '4° año')], null=True, verbose_name='Año de carrera')),
        migrations.AddField(model_name='estudiante', name='estado_avance', field=models.CharField(blank=True, choices=[('al_dia', 'Al día'), ('con_retraso', 'Con retraso')], default='', max_length=15, verbose_name='Situación académica declarada')),
    ]
