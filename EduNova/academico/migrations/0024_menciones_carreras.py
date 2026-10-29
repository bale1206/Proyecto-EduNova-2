"""Menciones de carreras; no cambia matrículas ni secciones anteriores."""
import django.db.models.deletion
from django.db import migrations, models


def cargar_mencion_verificada(apps, schema_editor):
    """Única mención confirmada por la malla PDF proporcionada (Duoc UC, 2026)."""
    Carrera = apps.get_model('academico', 'Carrera')
    Mencion = apps.get_model('academico', 'MencionCarrera')
    db = schema_editor.connection.alias
    carrera = Carrera.objects.using(db).filter(nombre__iexact='Ingeniería en Informática').first()
    if carrera:
        Mencion.objects.using(db).get_or_create(
            carrera_id=carrera.pk, nombre='Inteligencia Artificial',
            defaults={'activa': True},
        )


class Migration(migrations.Migration):
    dependencies = [('academico', '0023_estudiante_anio_ingreso')]

    operations = [
        migrations.CreateModel(
            name='MencionCarrera',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=160)),
                ('activa', models.BooleanField(default=True)),
                ('carrera', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name='menciones', to='academico.carrera')),
            ],
            options={'verbose_name': 'Mención de carrera',
                     'verbose_name_plural': 'Menciones de carreras',
                     'ordering': ['carrera__nombre', 'nombre']},
        ),
        migrations.AddConstraint(
            model_name='mencioncarrera',
            constraint=models.UniqueConstraint(fields=('carrera', 'nombre'), name='uq_mencion_carrera_nombre'),
        ),
        migrations.AddField(
            model_name='carreraasignatura', name='mencion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='plan_asignaturas', to='academico.mencioncarrera',
                                    verbose_name='Mención (opcional)',
                                    help_text='Deja vacío si la asignatura es común a todas las menciones.'),
        ),
        migrations.AddField(
            model_name='estudiante', name='mencion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='estudiantes', to='academico.mencioncarrera',
                                    verbose_name='Mención de carrera'),
        ),
        migrations.RemoveConstraint(model_name='carreraasignatura', name='uq_carrera_asignatura'),
        migrations.AddConstraint(
            model_name='carreraasignatura',
            constraint=models.UniqueConstraint(fields=('carrera', 'asignatura'),
                                               condition=models.Q(mencion__isnull=True),
                                               name='uq_carrera_asignatura_comun'),
        ),
        migrations.AddConstraint(
            model_name='carreraasignatura',
            constraint=models.UniqueConstraint(fields=('carrera', 'asignatura', 'mencion'),
                                               condition=models.Q(mencion__isnull=False),
                                               name='uq_carrera_asignatura_mencion'),
        ),
        migrations.RunPython(cargar_mencion_verificada, reverse_code=migrations.RunPython.noop),
    ]
