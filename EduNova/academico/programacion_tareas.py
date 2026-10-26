"""Repetición de tareas y fecha/hora de sus avisos internos (zona horaria de Django)."""
import calendar
from datetime import date, datetime, timedelta
from django.utils import timezone


def fechas_tarea(tarea, desde, hasta):
    """Fechas inclusivas; repetición mensual usa el día original o el último disponible."""
    inicial = tarea.fecha_limite
    if not inicial or tarea.completada or desde > hasta or inicial > hasta:
        return []
    modo = tarea.repeticion
    if modo == 'ninguna':
        return [inicial] if desde <= inicial <= hasta else []
    if modo in ('diaria', 'semanal'):
        paso = 1 if modo == 'diaria' else 7
        n = max(0, (desde - inicial).days // paso)
        actual = inicial + timedelta(days=n*paso)
        if actual < desde: actual += timedelta(days=paso)
        fechas=[]
        while actual <= hasta:
            fechas.append(actual)
            actual += timedelta(days=paso)
        return fechas
    if modo == 'mensual':
        y, m = desde.year, desde.month
        if (y,m) < (inicial.year,inicial.month): y,m = inicial.year,inicial.month
        fechas=[]
        while (y,m) <= (hasta.year,hasta.month):
            dia = min(inicial.day, calendar.monthrange(y,m)[1])
            actual = date(y,m,dia)
            if inicial <= actual <= hasta and desde <= actual: fechas.append(actual)
            m += 1
            if m == 13: y,m = y+1,1
        return fechas
    return []


def instante_aviso(tarea, fecha):
    if not tarea.hora_inicio: return None
    momento = datetime.combine(fecha, tarea.hora_inicio)
    if timezone.is_naive(momento): momento = timezone.make_aware(momento, timezone.get_current_timezone())
    return momento - timedelta(minutes=tarea.minutos_antes)
