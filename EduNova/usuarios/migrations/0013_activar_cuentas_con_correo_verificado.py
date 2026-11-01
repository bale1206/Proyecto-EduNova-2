"""Activa cuentas ya verificadas que el proceso anterior dejó pendientes.

No activa cuentas sin confirmación del código ni altera otros roles.
"""
from django.db import migrations


def activar_personal_ya_verificado(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    VerificacionCorreoRol = apps.get_model('usuarios', 'VerificacionCorreoRol')
    alias = schema_editor.connection.alias
    ids = VerificacionCorreoRol.objects.using(alias).filter(
        confirmado_en__isnull=False,
        usuario__rol__in=['docente', 'administrativo'],
        usuario__is_active=False,
        usuario__last_login__isnull=True,
    ).values_list('usuario_id', flat=True)
    Usuario.objects.using(alias).filter(
        pk__in=ids,
        rol__in=['docente', 'administrativo'],
        is_active=False,
        last_login__isnull=True,
    ).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0012_verificacion_correo_roles')]

    operations = [migrations.RunPython(activar_personal_ya_verificado,
                                      reverse_code=migrations.RunPython.noop)]
