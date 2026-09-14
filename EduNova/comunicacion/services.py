from django.db.models import Q

from academico.models import Curso
from .models import MensajeComunicacion


def cursos_relacionados(usuario):
    """Cursos con los que el usuario tiene relación (para filtrar comunicados por curso)."""
    if usuario.rol == usuario.Rol.DOCENTE:
        return Curso.objects.filter(docente_jefe=usuario)
    if usuario.rol == usuario.Rol.APODERADO:
        return Curso.objects.filter(estudiantes__apoderado=usuario).distinct()
    return Curso.objects.none()


def mensajes_para(usuario):
    """Mensajes que le corresponde ver a un usuario: directos o por curso."""
    cursos = cursos_relacionados(usuario)
    return MensajeComunicacion.objects.filter(
        Q(destinatario=usuario) | Q(curso_destino__in=cursos)
    ).exclude(remitente=usuario).distinct()


def mensajes_no_leidos(usuario):
    return mensajes_para(usuario).filter(leido=False)
