from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import PermissionDenied

from .models import MensajeComunicacion
from .services import mensajes_no_leidos, mensajes_para


@login_required
def enviar_comunicado(request):
    """Deshabilitado: los anuncios institucionales se realizan en Blackboard AVA.

    Se conserva la URL histórica, pero ninguna cuenta puede usarla para crear
    comunicados (incluso por POST directo). Los mensajes previos no se borran.
    """
    raise PermissionDenied('Los comunicados y anuncios se gestionan en Blackboard AVA.')


@login_required
def bandeja(request):
    mensajes = mensajes_para(request.user).select_related('remitente', 'curso_destino')
    return render(request, 'comunicacion/bandeja.html', {'mensajes': mensajes})


@login_required
def detalle_mensaje(request, mensaje_id):
    mensaje = get_object_or_404(mensajes_para(request.user), id=mensaje_id)
    if not mensaje.leido:
        from django.utils import timezone
        mensaje.leido = True
        mensaje.fecha_lectura = timezone.now()
        mensaje.save(update_fields=['leido', 'fecha_lectura'])
    return render(request, 'comunicacion/detalle_mensaje.html', {'mensaje': mensaje})


@login_required
def panel_notificaciones(request):
    """Fragmento HTMX que alimenta el dropdown de la campana de notificaciones."""
    notificaciones = mensajes_no_leidos(request.user).select_related('remitente')[:8]
    return render(request, 'comunicacion/_panel_notificaciones.html', {
        'notificaciones': notificaciones,
        'total_no_leidos': mensajes_no_leidos(request.user).count(),
    })
