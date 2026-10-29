"""Clases recurrentes para el calendario estudiantil (sin crear eventos ficticios).

La matrícula M2M Estudiante.secciones es la única fuente de secciones elegidas;
la oferta académica y sus HorarioSeccion son la fuente de días y horas.
No se generan ni persisten instancias de Evento.
"""
import calendar
from datetime import date

from .models import Curso


def fecha_en_periodo(fecha, periodo, *, hoy=None):
    """No presentar clases fuera del año/semestre de su oferta.

    Las secciones antiguas sin período solamente se dibujan en el semestre
    vigente, evitando repetir clases sin fecha indefinidamente.
    """
    if periodo is None:
        hoy = hoy or date.today()
        semestre = 1 if 3 <= hoy.month <= 7 else 2 if 8 <= hoy.month <= 12 else None
        return fecha.year == hoy.year and semestre is not None and (
            3 <= fecha.month <= 7 if semestre == 1 else 8 <= fecha.month <= 12
        )
    if fecha.year != periodo.anio:
        return False
    return (3 <= fecha.month <= 7) if periodo.semestre == 1 else (8 <= fecha.month <= 12)


def clases_por_dia(secciones, year, month, *, hoy=None):
    """Agrupa los bloques horarios de una sección en una clase por día.

    La fuente es la matrícula y sus horarios; nunca se crean eventos ficticios
    ni se mezclan dos secciones distintas de la misma asignatura.
    """
    resultado = {}
    ultimo = calendar.monthrange(year, month)[1]
    for seccion in secciones:
        periodo = seccion.periodo_academico
        horarios_por_semana = {}
        for horario in seccion.horarios.all():
            horarios_por_semana.setdefault(horario.dia_semana, []).append(horario)
        if not horarios_por_semana:
            continue
        for horarios in horarios_por_semana.values():
            horarios.sort(key=lambda h: (h.hora_inicio, h.hora_fin))
        for numero in range(1, ultimo + 1):
            fecha = date(year, month, numero)
            if not fecha_en_periodo(fecha, periodo, hoy=hoy):
                continue
            horarios = horarios_por_semana.get(fecha.isoweekday())
            if not horarios:
                continue
            resultado.setdefault(numero, []).append({
                'seccion_id': seccion.pk,
                'codigo': seccion.codigo_visible,
                'asignatura': seccion.asignatura_visible,
                'codigo_asignatura': seccion.codigo_asignatura_visible,
                'inicio': horarios[0].hora_inicio,
                'fin': max(hora.hora_fin for hora in horarios),
                'bloques': [
                    {'inicio': hora.hora_inicio, 'fin': hora.hora_fin}
                    for hora in horarios
                ],
            })
    for actividades in resultado.values():
        actividades.sort(key=lambda x: (x['inicio'], x['asignatura'], x['codigo']))
    return resultado


def secciones_eligibles(perfil):
    """Secciones del período y modalidad declarados, de su propia carrera.

    Usado tanto para visualizar la corrección de matrícula como para validar
    en servidor; el navegador no puede inscribir secciones ajenas.
    """
    from .models import Asignatura, CarreraAsignatura
    from usuarios.registro_guiado import _secciones_activas_registro

    if not perfil or not perfil.carrera_id:
        return Curso.objects.none()
    ids_asignaturas = CarreraAsignatura.objects.filter(
        carrera_id=perfil.carrera_id,
    ).values_list('asignatura_id', flat=True)
    qs = Curso.objects.filter(
        asignatura_catalogo_id__in=ids_asignaturas,
        asignatura_catalogo__activa=True,
    )
    if perfil.modalidad == 'diurno':
        qs = qs.filter(turno=True)
    elif perfil.modalidad == 'vespertino':
        qs = qs.filter(turno=False)
    else:
        # Una matrícula sin modalidad debe completarse desde Django Admin.
        return Curso.objects.none()
    return _secciones_activas_registro(qs).select_related(
        'asignatura_catalogo', 'periodo_academico',
    ).prefetch_related('horarios').order_by('asignatura_catalogo__nombre', 'codigo_institucional', 'seccion')
