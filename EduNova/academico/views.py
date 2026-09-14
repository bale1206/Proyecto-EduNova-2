import calendar as cal
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from comunicacion.services import mensajes_no_leidos
from usuarios.models import Usuario

from .forms import CursoForm, EventoForm
from .models import Asistencia, Curso, Estudiante, Evento

MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]


def _requerir_rol(request, rol):
    if request.user.rol != rol:
        raise PermissionDenied('No tienes acceso a esta sección.')


def _construir_calendario(year, month, eventos):
    """Arma una matriz de semanas (listas de días) con los eventos de cada día."""
    eventos_por_dia = {}
    for evento in eventos:
        eventos_por_dia.setdefault(evento.fecha.day, []).append(evento)

    cal.setfirstweekday(cal.MONDAY)
    semanas = []
    for semana in cal.monthcalendar(year, month):
        fila = []
        for dia in semana:
            fila.append({
                'numero': dia if dia != 0 else None,
                'eventos': eventos_por_dia.get(dia, []) if dia != 0 else [],
                'es_hoy': dia == date.today().day and month == date.today().month and year == date.today().year,
            })
        semanas.append(fila)
    return semanas


def _mes_actual_o_parametro(request):
    hoy = date.today()
    try:
        year = int(request.GET.get('year', hoy.year))
        month = int(request.GET.get('month', hoy.month))
        date(year, month, 1)
    except (ValueError, TypeError):
        year, month = hoy.year, hoy.month
    return year, month


def _mes_anterior_siguiente(year, month):
    anterior = (year - 1, 12) if month == 1 else (year, month - 1)
    siguiente = (year + 1, 1) if month == 12 else (year, month + 1)
    return anterior, siguiente


@login_required
def home_docente(request):
    _requerir_rol(request, Usuario.Rol.DOCENTE)

    cursos = Curso.objects.filter(docente_jefe=request.user)
    ahora = date.today()

    proxima_clase = (
        Evento.objects.filter(curso__in=cursos, tipo=Evento.Tipo.CLASE, fecha__gte=ahora)
        .order_by('fecha', 'hora_inicio')
        .first()
    )

    notificaciones = mensajes_no_leidos(request.user)[:8]
    total_no_leidos = mensajes_no_leidos(request.user).count()

    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    eventos_mes = Evento.objects.filter(curso__in=cursos, fecha__year=year, fecha__month=month)
    semanas = _construir_calendario(year, month, eventos_mes)

    contexto = {
        'cursos': cursos,
        'proxima_clase': proxima_clase,
        'notificaciones': notificaciones,
        'total_no_leidos': total_no_leidos,
        'semanas': semanas,
        'mes_nombre': MESES_ES[month],
        'anio': year,
        'mes': month,
        'prev_year': prev_y, 'prev_month': prev_m,
        'next_year': next_y, 'next_month': next_m,
    }
    if request.headers.get('HX-Request'):
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/home_docente.html', contexto)


@login_required
def home_apoderado(request):
    _requerir_rol(request, Usuario.Rol.APODERADO)

    estudiantes = Estudiante.objects.filter(apoderado=request.user).select_related('curso')

    familias = {}
    for estudiante in estudiantes:
        familias.setdefault(estudiante.apellido_familiar or 'Sin apellido', []).append(estudiante)

    total_no_leidos = mensajes_no_leidos(request.user).count()

    contexto = {
        'familias': familias,
        'total_no_leidos': total_no_leidos,
    }
    return render(request, 'academico/home_apoderado.html', contexto)


@login_required
def detalle_estudiante(request, estudiante_id):
    _requerir_rol(request, Usuario.Rol.APODERADO)
    estudiante = get_object_or_404(Estudiante, id=estudiante_id, apoderado=request.user)

    asistencias_recientes = Asistencia.objects.filter(estudiante=estudiante).order_by('-fecha')
    asistencia_actual = asistencias_recientes.first()

    ultimas_30 = asistencias_recientes[:30]
    total = len(ultimas_30)
    presentes = sum(1 for a in ultimas_30 if a.estado == Asistencia.Estado.PRESENTE)
    resumen_asistencia = round((presentes / total) * 100, 1) if total else None

    observaciones = estudiante.observaciones.filter(confidencial=False).order_by('-fecha')[:10]

    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    eventos_mes = Evento.objects.filter(curso=estudiante.curso, fecha__year=year, fecha__month=month) if estudiante.curso else Evento.objects.none()
    semanas = _construir_calendario(year, month, eventos_mes)

    proximas_evaluaciones = Evento.objects.filter(
        curso=estudiante.curso, tipo=Evento.Tipo.EVALUACION, fecha__gte=date.today(),
    ).order_by('fecha')[:5] if estudiante.curso else []

    contexto = {
        'estudiante': estudiante,
        'asistencia_actual': asistencia_actual,
        'resumen_asistencia': resumen_asistencia,
        'observaciones': observaciones,
        'proximas_evaluaciones': proximas_evaluaciones,
        'semanas': semanas,
        'mes_nombre': MESES_ES[month],
        'anio': year,
        'mes': month,
        'prev_year': prev_y, 'prev_month': prev_m,
        'next_year': next_y, 'next_month': next_m,
    }
    if request.headers.get('HX-Request'):
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/detalle_estudiante.html', contexto)


@login_required
def home_administrativo(request):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)

    cursos = Curso.objects.select_related('docente_jefe').all()

    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    eventos_mes = Evento.objects.filter(fecha__year=year, fecha__month=month).select_related('curso')
    semanas = _construir_calendario(year, month, eventos_mes)

    contexto = {
        'cursos': cursos,
        'total_estudiantes': Estudiante.objects.count(),
        'proximos_eventos': Evento.objects.filter(fecha__gte=date.today()).select_related('curso').order_by('fecha', 'hora_inicio')[:8],
        'curso_form': CursoForm(),
        'evento_form': EventoForm(),
        'semanas': semanas,
        'mes_nombre': MESES_ES[month],
        'anio': year,
        'mes': month,
        'prev_year': prev_y, 'prev_month': prev_m,
        'next_year': next_y, 'next_month': next_m,
    }
    if request.headers.get('HX-Request'):
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/home_administrativo.html', contexto)


@login_required
def crear_curso(request):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    if request.method == 'POST':
        form = CursoForm(request.POST)
        if form.is_valid():
            curso = form.save()
            messages.success(request, f'Curso "{curso.grado_curso}" creado.')
            return redirect('academico:home_administrativo')
        messages.error(request, 'Revisa los datos del curso: ' + '; '.join(form.errors))
    return redirect('academico:home_administrativo')


@login_required
def crear_evento(request):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    if request.method == 'POST':
        form = EventoForm(request.POST)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.creado_por = request.user
            evento.save()
            messages.success(request, f'"{evento.titulo}" agendado para {evento.curso}.')
            return redirect('academico:home_administrativo')
        messages.error(request, 'Revisa los datos del evento: ' + '; '.join(form.errors))
    return redirect('academico:home_administrativo')
