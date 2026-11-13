"""Creación segura de eventos y tareas personales para docentes y directores.

No utiliza carreras, asignaturas ni secciones del catálogo histórico. Los errores
esperables se comunican sin generar respuestas HTTP 500, y los fallos de base de
datos quedan registrados en los logs para diagnóstico (no se silencian).
"""
import logging
import re
from datetime import date, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from usuarios.models import Usuario
from .models import Evento, TareaEstudio

logger = logging.getLogger(__name__)


def _portal(usuario):
    return 'academico:home_docente' if usuario.rol == Usuario.Rol.DOCENTE else 'academico:home_administrativo'


def _fecha_requerida(valor):
    if not valor:
        raise ValueError('Selecciona una fecha para la actividad.')
    try:
        fecha = date.fromisoformat(valor)
    except (ValueError, TypeError):
        raise ValueError('La fecha no tiene un formato válido.') from None
    return fecha


def _hora_opcional(valor):
    if not valor:
        return None
    if not re.fullmatch(r'\d{2}:\d{2}(?::\d{2})?', valor):
        raise ValueError('Las horas deben tener formato HH:MM.')
    try:
        valor_hora = time.fromisoformat(valor)
    except ValueError:
        raise ValueError('Indica una hora válida en formato de 24 horas.') from None
    if valor_hora.tzinfo is not None:
        raise ValueError('Las horas deben ser locales, sin zona horaria.')
    return valor_hora


@login_required
@require_POST
def crear_evento(request):
    """Reuniones, eventos y evaluaciones privados (evaluación solo docente)."""
    usuario = request.user
    if usuario.rol not in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
        raise PermissionDenied('Solo docentes y directores pueden crear estos eventos.')
    destino = _portal(usuario)
    tipo = request.POST.get('tipo', '')
    tipos_permitidos = ({Evento.Tipo.REUNION, Evento.Tipo.OTRO, Evento.Tipo.EVALUACION}
                        if usuario.rol == Usuario.Rol.DOCENTE else
                        {Evento.Tipo.REUNION, Evento.Tipo.OTRO})
    if tipo not in tipos_permitidos:
        raise PermissionDenied('Este tipo de actividad no está disponible para tu perfil.')
    titulo = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    if not titulo or len(titulo) > 150:
        messages.error(request, 'Escribe un título de entre 1 y 150 caracteres.')
        return redirect(destino)
    if len(descripcion) > 5000:
        messages.error(request, 'La descripción no debe superar 5.000 caracteres.')
        return redirect(destino)
    try:
        fecha = _fecha_requerida(request.POST.get('fecha'))
        inicio = _hora_opcional(request.POST.get('hora_inicio', ''))
        fin = _hora_opcional(request.POST.get('hora_fin', ''))
        if fin and not inicio:
            raise ValueError('Indica una hora de inicio si escribes una hora de término.')
        if inicio and fin and fin <= inicio:
            raise ValueError('La hora de término debe ser posterior a la de inicio.')
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(destino)
    try:
        with transaction.atomic():
            Evento.objects.create(
                tipo=tipo, titulo=titulo, descripcion=descripcion,
                fecha=fecha, hora_inicio=inicio, hora_fin=fin,
                creado_por=usuario, curso=None, carrera=None,
            )
    except DatabaseError:
        logger.exception('No se pudo guardar un evento personal: rol=%s usuario_id=%s', usuario.rol, usuario.pk)
        messages.error(request,
            'No se pudo guardar la actividad por un problema de base de datos. '
            'Contacta a soporte para revisar las migraciones del calendario.')
        return redirect(destino)
    messages.success(request, 'Actividad guardada en tu calendario personal.')
    return redirect(destino)


@login_required
@require_POST
def crear_tarea_equipo(request):
    """Tareas personales de docentes. Los directores conservan eventos/reuniones."""
    usuario = request.user
    if usuario.rol != Usuario.Rol.DOCENTE:
        raise PermissionDenied('Las tareas personales están disponibles únicamente para docentes.')
    destino = _portal(usuario)
    titulo = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    if not titulo or len(titulo) > 160:
        messages.error(request, 'Escribe un título de entre 1 y 160 caracteres.')
        return redirect(destino)
    if len(descripcion) > 2000:
        messages.error(request, 'La descripción no debe superar 2.000 caracteres.')
        return redirect(destino)
    try:
        fecha = _fecha_requerida(request.POST.get('fecha_limite'))
        hora = _hora_opcional(request.POST.get('hora_inicio', ''))
        if hora is None:
            raise ValueError('Indica la hora de inicio de tu tarea.')
        minutos_antes = int(request.POST.get('minutos_antes', '15'))
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc) if isinstance(exc, ValueError) and exc.args and not str(exc).startswith('invalid literal')
                       else 'Revisa la fecha, la hora y la antelación de la tarea.')
        return redirect(destino)
    repeticion = request.POST.get('repeticion', 'ninguna')
    prioridad = request.POST.get('prioridad', 'media')
    color = request.POST.get('color', '#4C849D').upper()
    if repeticion not in ('ninguna', 'diaria', 'semanal', 'mensual'):
        messages.error(request, 'Selecciona una repetición válida.')
        return redirect(destino)
    if prioridad not in ('alta', 'media', 'baja'):
        messages.error(request, 'Selecciona una prioridad válida.')
        return redirect(destino)
    if minutos_antes not in (0, 5, 10, 15, 30, 60):
        messages.error(request, 'Selecciona una antelación válida.')
        return redirect(destino)
    if not re.fullmatch(r'#[0-9A-F]{6}', color):
        color = '#4C849D'
    try:
        with transaction.atomic():
            tarea = TareaEstudio.objects.create(
                estudiante=usuario, seccion=None, titulo=titulo, descripcion=descripcion,
                fecha_limite=fecha, hora_inicio=hora, repeticion=repeticion,
                prioridad=prioridad, minutos_antes=minutos_antes, color=color,
            )
    except DatabaseError:
        logger.exception('No se pudo guardar una tarea docente: usuario_id=%s', usuario.pk)
        messages.error(request,
            'No se pudo guardar la tarea por un problema de base de datos. '
            'Contacta a soporte para revisar las migraciones de actividades.')
        return redirect(destino)
    return redirect(f"{reverse(destino)}?configurar_tarea={tarea.pk}#configurar-recordatorio")
