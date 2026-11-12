from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from usuarios.models import Usuario
from .horario_personal import leer_horario, MAX_BYTES
from .models import BloqueHorarioPersonal

PENDIENTE = 'edunova_horario_previo_v1'


def _autorizar(usuario):
    if usuario.rol not in (Usuario.Rol.ESTUDIANTE, Usuario.Rol.DOCENTE):
        raise PermissionDenied('La importación de horario está disponible para estudiantes y docentes.')


@login_required
@require_http_methods(['GET'])
def plantilla_horario(request):
    _autorizar(request.user)
    return FileResponse(open(Path(settings.BASE_DIR) / 'plantillas/horario-edunova.xlsx', 'rb'),
                        as_attachment=True, filename='horario-edunova.xlsx',
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@login_required
@require_http_methods(['GET', 'POST'])
def importar_horario(request):
    _autorizar(request.user)
    error = ''
    if request.method == 'POST':
        accion = request.POST.get('accion', 'previsualizar')
        if accion == 'cancelar':
            request.session.pop(PENDIENTE, None)
            return redirect('academico:importar_horario')
        if accion == 'aplicar':
            previo = request.session.get(PENDIENTE)
            if not previo or previo.get('usuario') != request.user.pk:
                error = 'Carga primero un archivo para revisarlo.'
            elif request.POST.get('confirmar') != 'si':
                error = 'Confirma que deseas reemplazar tu horario personal.'
            else:
                with transaction.atomic():
                    # Serializa importaciones concurrentes de la misma cuenta.
                    Usuario.objects.select_for_update().get(pk=request.user.pk)
                    BloqueHorarioPersonal.objects.filter(usuario=request.user).delete()
                    BloqueHorarioPersonal.objects.bulk_create([
                        BloqueHorarioPersonal(usuario=request.user, **fila) for fila in previo['bloques']])
                request.session.pop(PENDIENTE, None)
                messages.success(request, 'Horario importado. Tus clases ya aparecen en el calendario.')
                fecha = min(b['fecha_inicio'] for b in previo['bloques'])
                destino = 'academico:home_estudiante' if request.user.rol == Usuario.Rol.ESTUDIANTE else 'academico:home_docente'
                return redirect(f'{reverse(destino)}?year={fecha[:4]}&month={int(fecha[5:7])}')
        elif accion == 'previsualizar':
            request.session.pop(PENDIENTE, None)
            archivo = request.FILES.get('archivo')
            try:
                if not archivo or archivo.size > MAX_BYTES:
                    raise ValueError('Selecciona un archivo .xlsx de hasta 5 MB.')
                filas = leer_horario(archivo.read(MAX_BYTES + 1), archivo.name)
                request.session[PENDIENTE] = {'usuario': request.user.pk, 'bloques': filas}
            except ValueError as exc:
                error = str(exc)
        else:
            error = 'Acción no reconocida.'
    previo = request.session.get(PENDIENTE, {})
    return render(request, 'academico/importar_horario.html', {
        'error': error, 'previo': previo.get('bloques') if previo.get('usuario') == request.user.pk else None,
        'bloques_actuales': BloqueHorarioPersonal.objects.filter(usuario=request.user),
    })
