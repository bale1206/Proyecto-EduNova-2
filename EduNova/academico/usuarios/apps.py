import sys

from django.apps import AppConfig
from django.conf import settings


class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'

    def ready(self):
        # Solo en desarrollo (DEBUG=True) y solo cuando el comando es
        # literalmente "runserver": cada vez que se levanta el servidor
        # se cierran todas las sesiones activas, para no dejar colgada
        # una sesión (p. ej. de un administrador) entre una corrida de
        # "runserver" y la siguiente. No se activa con migrate, test,
        # shell, createsuperuser, etc. En producción (DEBUG=False) se
        # desactiva solo, porque ahí sí quieres que la gente siga
        # logueada aunque el servidor se reinicie.
        es_runserver = len(sys.argv) > 1 and sys.argv[1] == 'runserver'
        if settings.DEBUG and es_runserver:
            self._cerrar_sesiones_activas()

    def _cerrar_sesiones_activas(self):
        from django.contrib.sessions.models import Session
        try:
            Session.objects.all().delete()
        except Exception:
            # La tabla de sesiones puede no existir aún (antes del primer
            # "migrate") — no es un error real, solo no hay nada que borrar.
            pass
