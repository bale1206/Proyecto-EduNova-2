from django.db import migrations, models
import django.db.models.deletion

CARRERAS = [
    ('Informática y Telecomunicaciones', 'Ingeniería en Informática'),
    ('Informática y Telecomunicaciones', 'Ingeniería en Infraestructura Tecnológica'),
    ('Informática y Telecomunicaciones', 'Ingeniería en Redes y Telecomunicaciones'),
    ('Turismo y Hospitalidad', 'Administración en Turismo y Hospitalidad'),
    ('Administración y Negocios', 'Ingeniería en Marketing Digital'),
    ('Administración y Negocios', 'Auditoría'),
    ('Administración y Negocios', 'Ingeniería en Gestión Logística'),
    ('Administración y Negocios', 'Ingeniería en Comercio Exterior'),
    ('Administración y Negocios', 'Ingeniería en Administración Mención Gestión de Personas'),
    ('Administración y Negocios', 'Ingeniería en Administración Mención Innovación y Emprendimiento'),
    ('Administración y Negocios', 'Ingeniería en Administración Mención Finanzas'),
    ('Administración y Negocios', 'Técnico en Administración'),
    ('Gastronomía', 'Gastronomía Internacional'),
]

def poblar_carreras(apps, schema_editor):
    Carrera = apps.get_model('academico', 'Carrera')
    for escuela, nombre in CARRERAS:
        Carrera.objects.using(schema_editor.connection.alias).get_or_create(nombre=nombre, defaults={'escuela': escuela})

def migrar_secciones_existentes(apps, schema_editor):
    Estudiante = apps.get_model('academico', 'Estudiante')
    through = Estudiante.secciones.through
    alias = schema_editor.connection.alias
    for estudiante in Estudiante.objects.using(alias).exclude(curso_id__isnull=True).iterator():
        through.objects.using(alias).get_or_create(estudiante_id=estudiante.pk, curso_id=estudiante.curso_id)

class Migration(migrations.Migration):
    dependencies = [('academico', '0009_correlativo_unico')]
    operations = [
        migrations.CreateModel(name='Carrera', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('escuela', models.CharField(max_length=120)),
            ('nombre', models.CharField(max_length=180, unique=True)),
            ('activa', models.BooleanField(default=True)),
        ], options={'ordering':['escuela','nombre'], 'verbose_name':'Carrera', 'verbose_name_plural':'Carreras'}),
        migrations.AlterModelOptions(name='curso', options={'ordering': ['seccion'], 'verbose_name': 'Asignatura y sección', 'verbose_name_plural': 'Asignaturas y secciones'}),
        migrations.AddField(model_name='estudiante', name='carrera', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estudiantes', to='academico.carrera')),
        migrations.AddField(model_name='estudiante', name='secciones', field=models.ManyToManyField(blank=True, related_name='matriculados', to='academico.curso', verbose_name='Asignaturas / secciones inscritas')),
        migrations.RunPython(poblar_carreras, migrations.RunPython.noop),
        migrations.RunPython(migrar_secciones_existentes, migrations.RunPython.noop),
    ]
