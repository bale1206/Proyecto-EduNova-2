"""Múltiples menciones impartidas por docente, vinculadas al catálogo académico."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0009_directores_multiples_carreras'),
        ('academico', '0024_menciones_carreras'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario', name='menciones_docencia',
            field=models.ManyToManyField(blank=True,
                related_name='docentes_registrados', to='academico.mencioncarrera',
                verbose_name='Menciones en las que imparte clases'),
        ),
    ]
