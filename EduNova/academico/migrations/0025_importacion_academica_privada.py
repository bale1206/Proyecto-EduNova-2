"""Importador académico privado: versionado de mallas y ofertas por período.

Migration ADITIVA; no elimina datos ni renombra identificadores antiguos.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('academico', '0024_menciones_carreras'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PeriodoAcademico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anio', models.PositiveSmallIntegerField()),
                ('semestre', models.PositiveSmallIntegerField(choices=[(1,'Primer semestre'),(2,'Segundo semestre')])),
                ('sede', models.CharField(max_length=100, default='Antonio Varas')),
            ],
            options={'ordering':['-anio','-semestre','sede'], 'verbose_name':'Período académico', 'verbose_name_plural':'Períodos académicos'},
        ),
        migrations.AddConstraint(
            model_name='periodoacademico',
            constraint=models.UniqueConstraint(fields=['anio','semestre','sede'], name='uq_periodo_anio_semestre_sede'),
        ),
        migrations.CreateModel(
            name='PlanEstudio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anio_ingreso', models.PositiveSmallIntegerField(verbose_name='Año de ingreso de la cohorte')),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('carrera', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='planes_estudio', to='academico.carrera')),
                ('mencion', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='planes_estudio', to='academico.mencioncarrera')),
            ],
            options={'ordering':['carrera__nombre','-anio_ingreso'], 'verbose_name':'Versión de malla curricular', 'verbose_name_plural':'Versiones de mallas curriculares'},
        ),
        migrations.AddConstraint(
            model_name='planestudio',
            constraint=models.UniqueConstraint(fields=['carrera','anio_ingreso'], condition=models.Q(mencion__isnull=True), name='uq_plan_comun_ingreso'),
        ),
        migrations.AddConstraint(
            model_name='planestudio',
            constraint=models.UniqueConstraint(fields=['carrera','mencion','anio_ingreso'], condition=models.Q(mencion__isnull=False), name='uq_plan_mencion_ingreso'),
        ),
        migrations.CreateModel(
            name='PlanAsignatura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anio_curricular', models.PositiveSmallIntegerField(choices=[(i,f'{i}° año') for i in range(1,5)])),
                ('semestre_curricular', models.PositiveSmallIntegerField(choices=[(1,'Primero'),(2,'Segundo')])),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaturas', to='academico.planestudio')),
                ('asignatura', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='planes_versionados', to='academico.asignatura')),
            ],
            options={'verbose_name':'Asignatura en versión de malla', 'verbose_name_plural':'Asignaturas de versiones de mallas'},
        ),
        migrations.AddConstraint(
            model_name='planasignatura',
            constraint=models.UniqueConstraint(fields=['plan','asignatura'], name='uq_asignatura_version_malla'),
        ),
        migrations.CreateModel(
            name='ImportacionAcademica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(max_length=10, choices=[('malla','Malla curricular'),('oferta','Oferta semestral')])),
                ('estado', models.CharField(max_length=12, choices=[('aplicada','Aplicada'),('pendiente','Pendiente de transcripción')])),
                ('archivo_nombre', models.CharField(max_length=240)),
                ('archivo_privado', models.CharField(max_length=120, blank=True)),
                ('sha256', models.CharField(max_length=64)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('resumen', models.JSONField(default=dict, blank=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='importaciones_academicas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering':['-creado_en'], 'verbose_name':'Importación académica', 'verbose_name_plural':'Importaciones académicas'},
        ),
        migrations.AddField(
            model_name='curso', name='periodo_academico',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='secciones', to='academico.periodoacademico', verbose_name='Período académico'),
        ),
        migrations.AddField(
            model_name='curso', name='codigo_institucional',
            field=models.CharField(max_length=45, blank=True, db_index=True, verbose_name='Código de sección en Duoc UC', help_text='Ej.: OCY1104-001D. El identificador interno se conserva.'),
        ),
        migrations.AddField(
            model_name='curso', name='docentes_oferta',
            field=models.TextField(blank=True, verbose_name='Docentes informados en la oferta', help_text='Nombres oficiales; no equivalen a cuentas verificadas.'),
        ),
        migrations.AddConstraint(
            model_name='curso',
            constraint=models.UniqueConstraint(fields=['periodo_academico','asignatura_catalogo','codigo_institucional'], condition=models.Q(periodo_academico__isnull=False) & ~models.Q(codigo_institucional=''), name='uq_oferta_periodo_asig_codigo'),
        ),
    ]
