import unicodedata

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import academico.secciones


def migrar_secciones(apps, schema_editor):
    Curso = apps.get_model('academico', 'Curso')
    db = schema_editor.connection.alias
    contadores = {}
    for curso in Curso.objects.using(db).order_by('pk'):
        nombre = curso.asignatura.strip()
        normalizado = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
        letras = ''.join(c for c in normalizado.upper() if 'A' <= c <= 'Z')
        # Se conserva el nombre anterior mientras se completa la asignatura real.
        if len(letras) < 3:
            nombre = 'Curso ' + nombre
            letras = 'CUR'
        prefijo = letras[:3]
        numero = contadores.get(prefijo, 0)
        contadores[prefijo] = numero + 1
        Curso.objects.using(db).filter(pk=curso.pk).update(
            asignatura=nombre, seccion=f'{prefijo}-{numero:03d}D', turno=True,
        )


class Migration(migrations.Migration):
    dependencies = [('academico', '0007_sanciones_observaciones')]
    operations = [
        migrations.RenameField(model_name='curso', old_name='grado_curso', new_name='asignatura'),
        migrations.AlterField(model_name='curso', name='asignatura', field=models.CharField('Asignatura', max_length=150, validators=[academico.secciones.validar_asignatura])),
        migrations.AddField(model_name='curso', name='turno', field=models.BooleanField('Turno', default=True, choices=[(True, 'Diurno'), (False, 'Vespertino')])),
        migrations.AddField(model_name='curso', name='seccion', field=models.CharField('Sección', max_length=50, null=True, editable=False)),
        migrations.RunPython(migrar_secciones, migrations.RunPython.noop),
        migrations.AlterField(model_name='curso', name='seccion', field=models.CharField('Sección', max_length=50, unique=True, editable=False, validators=[academico.secciones.validar_seccion])),
        migrations.AlterModelOptions(name='curso', options={'ordering': ['seccion'], 'verbose_name': 'Curso', 'verbose_name_plural': 'Cursos'}),
        migrations.AlterField(model_name='estudiante', name='apoderado', field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='estudiantes_a_cargo', limit_choices_to={'rol': 'apoderado'})),
    ]
