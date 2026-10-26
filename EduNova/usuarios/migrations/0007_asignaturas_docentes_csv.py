from django.db import migrations, models

def copiar_asignaturas_anteriores(apps, schema_editor):
    """Recuperar asociaciones desde secciones sin perder asignaciones existentes."""
    Usuario = apps.get_model('usuarios', 'Usuario')
    Curso = apps.get_model('academico', 'Curso')
    db = schema_editor.connection.alias
    through = Usuario.asignaturas_asociadas.through
    for seccion in Curso.objects.using(db).exclude(asignatura_catalogo_id__isnull=True).iterator():
        docentes = set(seccion.docentes.using(db).values_list('pk', flat=True))
        if seccion.docente_jefe_id:
            docentes.add(seccion.docente_jefe_id)
        for docente_id in docentes:
            if Usuario.objects.using(db).filter(pk=docente_id, rol='docente').exists():
                through.objects.using(db).get_or_create(usuario_id=docente_id, asignatura_id=seccion.asignatura_catalogo_id)


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0006_alter_usuario_curso'), ('academico', '0016_eliminar_secciones_conservar_historial')]
    operations = [
        migrations.AddField(model_name='usuario', name='asignaturas_asociadas', field=models.ManyToManyField(blank=True, limit_choices_to={'activa': True}, related_name='docentes_asociados', to='academico.asignatura', verbose_name='Asignaturas asociadas (docente)')),
        migrations.RunPython(copiar_asignaturas_anteriores, migrations.RunPython.noop),
    ]
