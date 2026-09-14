from .services import mensajes_no_leidos


def notificaciones(request):
    if request.user.is_authenticated:
        return {'total_no_leidos_global': mensajes_no_leidos(request.user).count()}
    return {}
