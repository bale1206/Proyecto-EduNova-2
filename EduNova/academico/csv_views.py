from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from usuarios.models import Usuario
from .csv_services import ErrorCSV, cargar_csv, esquema, respuesta_csv, respuesta_ejemplo_csv, filas_ejemplo_csv, tablas_disponibles
from .models import PermisoTablaCSV


def _rol(request, role):
    if request.user.rol != role:
        raise PermissionDenied('No tienes acceso a esta sección.')


def _tabla_autorizada(request, tabla, accion):
    _rol(request, Usuario.Rol.ADMINISTRATIVO)
    model = tablas_disponibles().get(tabla)
    if model is None:
        raise PermissionDenied('Tabla no disponible para CSV.')
    permission = get_object_or_404(PermisoTablaCSV, tabla=tabla)
    if not getattr(permission, accion):
        raise PermissionDenied('El director no autorizó esta operación.')
    return model, permission


@login_required
@require_http_methods(['GET', 'POST'])
def configurar_csv(request):
    _rol(request, Usuario.Rol.ADMINISTRATIVO)
    available = tablas_disponibles()
    if request.method == 'POST':
        from django.db import transaction
        exports = set(request.POST.getlist('exportar'))
        imports = set(request.POST.getlist('importar'))
        if (exports | imports) - available.keys():
            raise PermissionDenied('La selección contiene tablas no disponibles.')
        with transaction.atomic():
            for table in available:
                PermisoTablaCSV.objects.update_or_create(
                    tabla=table, defaults={'exportar': table in exports, 'importar': table in imports}
                )
        messages.success(request, 'Permisos guardados. Se aplican a todos los administrativos.')
        return redirect('academico:configurar_csv')
    permissions = {p.tabla: p for p in PermisoTablaCSV.objects.all()}
    tables = [
        {'nombre': name, 'etiqueta': model._meta.verbose_name_plural,
         'permiso': permissions.get(name), 'columnas': esquema(model)}
        for name, model in sorted(available.items())
    ]
    return render(request, 'academico/configurar_csv.html', {'tablas': tables})


@login_required
@require_GET
def panel_csv(request):
    _rol(request, Usuario.Rol.ADMINISTRATIVO)
    available = tablas_disponibles()
    tables = []
    for permission in PermisoTablaCSV.objects.order_by('tabla'):
        model = available.get(permission.tabla)
        if model and (permission.exportar or permission.importar):
            tables.append({'nombre': permission.tabla, 'permiso': permission,
                           'etiqueta': model._meta.verbose_name_plural, 'columnas': esquema(model),
                           'ejemplos': filas_ejemplo_csv(model) if permission.tabla in ('academico_curso', 'academico_estudiante') else []})
    return render(request, 'academico/panel_csv.html', {'tablas': tables})


@login_required
@require_GET
def exportar_csv(request, tabla):
    model, _ = _tabla_autorizada(request, tabla, 'exportar')
    return respuesta_csv(model)


@login_required
@require_GET
def plantilla_csv(request, tabla):
    model, _ = _tabla_autorizada(request, tabla, 'importar')
    return respuesta_csv(model, plantilla=True)


@login_required
@require_POST
def importar_csv(request, tabla):
    model, permission = _tabla_autorizada(request, tabla, 'importar')
    archivo = request.FILES.get('archivo')
    if archivo is None:
        messages.error(request, 'Selecciona el archivo CSV que deseas importar.')
    else:
        try:
            count = cargar_csv(model, archivo, permission.pk)
        except ErrorCSV as exc:
            messages.error(request, f'No se importó ningún registro. {exc}')
        else:
            messages.success(request, f'Se añadieron {count} registros a {tabla}.')
    return redirect('academico:panel_csv')


@login_required
@require_GET
def ejemplo_csv(request, tabla):
    model, _ = _tabla_autorizada(request, tabla, 'importar')
    if tabla not in ('academico_curso', 'academico_estudiante'):
        raise PermissionDenied('No hay ejemplos disponibles para esta tabla.')
    return respuesta_ejemplo_csv(model)
