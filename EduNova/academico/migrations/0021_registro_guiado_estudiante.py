from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('academico', '0020_planificacion_compartida')]

    operations = [
        migrations.AddField(model_name='carreraasignatura', name='anio_plan', field=models.PositiveSmallIntegerField(blank=True, null=True, choices=[(1, '1° año'), (2, '2° año'), (3, '3° año'), (4, '4° año')], verbose_name='Año curricular')),
        migrations.AddField(model_name='carreraasignatura', name='semestre_plan', field=models.PositiveSmallIntegerField(blank=True, null=True, choices=[(1, 'Primer semestre'), (2, 'Segundo semestre')], verbose_name='Semestre curricular')),
        migrations.CreateModel(
            name='HorarioSeccion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dia_semana', models.PositiveSmallIntegerField(choices=[(1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo')])),
                ('hora_inicio', models.TimeField()),
                ('hora_fin', models.TimeField()),
                ('seccion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='horarios', to='academico.curso')),
            ],
            options={'verbose_name': 'Horario de sección', 'verbose_name_plural': 'Horarios de secciones', 'ordering': ['dia_semana', 'hora_inicio']},
        ),
        migrations.AddConstraint(model_name='horarioseccion', constraint=models.UniqueConstraint(fields=('seccion', 'dia_semana', 'hora_inicio'), name='uq_horario_seccion_inicio')),
    ]
