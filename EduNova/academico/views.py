import calendar as cal
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from comunicacion.services import mensajes_no_leidos
from usuarios.models import Usuario

from .forms import CursoForm, EventoForm, JustificacionRetiroForm, ObservacionForm, ActualizarObservacionForm
from django.db.models import Case, When, Value, IntegerField
from .models import Asistencia, Curso, Estudiante, Evento, JustificacionRetiro, ObservacionComportamiento, RegistroAsistencia
from django.http import JsonResponse
from comunicacion.models import MensajeComunicacion

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

    justificaciones = estudiante.justificaciones.order_by('-creado_en')[:10]

    contexto = {
        'estudiante': estudiante,
        'asistencia_actual': asistencia_actual,
        'resumen_asistencia': resumen_asistencia,
        'observaciones': observaciones,
        'proximas_evaluaciones': proximas_evaluaciones,
        'justificaciones': justificaciones,
        'justificacion_form': JustificacionRetiroForm(),
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


@login_required
def crear_justificacion(request, estudiante_id):
    _requerir_rol(request, Usuario.Rol.APODERADO)
    estudiante = get_object_or_404(Estudiante, id=estudiante_id, apoderado=request.user)

    if request.method == 'POST':
        form = JustificacionRetiroForm(request.POST, request.FILES)
        if form.is_valid():
            justificacion = form.save(commit=False)
            justificacion.estudiante = estudiante
            justificacion.apoderado = request.user
            justificacion.save()
            messages.success(request, 'Justificación enviada. Quedará pendiente hasta que el colegio la revise.')
        else:
            messages.error(request, 'Revisa los datos de la justificación: ' + '; '.join(form.errors))

    return redirect('academico:detalle_estudiante', estudiante_id=estudiante.id)

@login_required
def crear_observacion(request):
    if request.method == 'POST':
        form = ObservacionForm(request.POST, user=request.user)
        if form.is_valid():
            observacion = form.save(commit=False)
            # Se asigna automáticamente el docente logueado
            observacion.docente = request.user
            observacion.save()
            # Necesario para guardar las relaciones Muchos-a-Muchos (Estudiantes)
            form.save_m2m() 
            return redirect('academico:home_docente')
    else:
        form = ObservacionForm(user=request.user)
    
    return render(request, 'academico/crear_observacion.html', {'form': form})

@login_required
def editar_observacion(request, pk):
    observacion = get_object_or_404(ObservacionComportamiento, pk=pk)
    
    if request.method == 'POST':
        form = ObservacionForm(request.POST, instance=observacion, user=request.user)
        if form.is_valid():
            obs = form.save(commit=False)
            
            # Si un administrativo está editando, queda registrado automáticamente
            if request.user.groups.filter(name='Administrativo').exists():
                obs.administrativo = request.user
                
            obs.save()
            form.save_m2m()
            return redirect('academico:home_docente')
    else:
        form = ObservacionForm(instance=observacion, user=request.user)
        
    return render(request, 'academico/editar_observacion.html', {'form': form})

def cargar_estudiantes(request):
    curso_id = request.GET.get('curso_id')
    
    # Filtramos los estudiantes que pertenecen al curso seleccionado
    if curso_id:
        estudiantes = Estudiante.objects.filter(curso_id=curso_id).order_by('nombre_completo')
        
        # OJO: Cambia 'nombre' por los campos que tengas en tu modelo Estudiante (ej: 'nombres', 'apellidos')
        # values() transforma el QuerySet en una lista de diccionarios para poder convertirlo a JSON
        data = list(estudiantes.values('id', 'nombre_completo')) 
    else:
        data = []
        
    return JsonResponse(data, safe=False)

@login_required
def lista_observaciones(request):
    # Ocultamos las "RESUELTA" según las instrucciones
    observaciones = ObservacionComportamiento.objects.exclude(estado='RESUELTA').annotate(
        # Priorizamos Estados: 1. NO_VISTA, 2. EN_PROCESO
        prioridad_estado=Case(
            When(estado='NO_VISTA', then=Value(1)),
            When(estado='EN_PROCESO', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ),
        # Priorizamos Tipos: 1. NEGATIVA, 2. ESPECIALISTA
        prioridad_tipo=Case(
            When(tipo_observacion='NEGATIVA', then=Value(1)),
            When(tipo_observacion='ESPECIALISTA', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by(
        'prioridad_estado',       # Primero por estado
        'prioridad_tipo',         # Luego por tipo
        '-fecha_actualizacion'    # Finalmente por fecha descendente
    )

    return render(request, 'academico/lista_observaciones.html', {'observaciones': observaciones})

@login_required
def actualizar_observacion(request, pk):
    observacion = get_object_or_404(ObservacionComportamiento, pk=pk)
    
    if request.method == 'POST':
        form = ActualizarObservacionForm(request.POST, instance=observacion)
        if form.is_valid():
            obs = form.save(commit=False)
            obs.administrativo = request.user
            obs.save()
            
            # Si el administrativo marcó la casilla "Notificar apoderado"
            if form.cleaned_data.get('notificar_apoderado'):
                
                # Iteramos sobre todos los estudiantes en esta observación
                for estudiante in obs.estudiantes.all():
                    # Verificamos que el estudiante tenga un apoderado asignado
                    # (Ajusta 'estudiante.apoderado' a la relación exacta en tus modelos)
                    if hasattr(estudiante, 'apoderado') and estudiante.apoderado:
                        
                        # Creamos la notificación interna
                        # Creamos la notificación interna
                        MensajeComunicacion.objects.create(
                            remitente=request.user,  
                            destinatario=estudiante.apoderado,
                            asunto=f"Actualización de Observación: {obs.asunto}",
                            cuerpo_mensaje=(
                                f"Estimado apoderado,\n\n"
                                f"Se ha actualizado una observación de comportamiento para su pupilo {estudiante.nombre_completo}.\n\n"
                                f"Estado: {obs.get_estado_display()}\n"
                                f"Resolución Administrativa:\n{obs.resolucion}\n\n"
                                f"Saludos cordiales."
                            ),
                            tipo_comunicacion='disciplinario' # Aprovechamos las opciones de tu modelo
                        )
                
                messages.success(request, "Observación actualizada y apoderado(s) notificado(s) correctamente.")
            else:
                messages.success(request, "Observación actualizada correctamente.")
            
            return redirect('academico:lista_observaciones')
    else:
        form = ActualizarObservacionForm(instance=observacion)
        
    return render(request, 'academico/actualizar_observacion.html', {
        'form': form,
        'observacion': observacion
    })

@login_required
def tomar_asistencia(request):
    if request.method == 'POST':
        # Obtenemos la lista de todos los IDs de estudiantes enviados en el formulario
        estudiantes_ids = request.POST.getlist('estudiante_id')
        
        for est_id in estudiantes_ids:
            estudiante = get_object_or_404(Estudiante, pk=est_id)
            # Rescatamos el valor del radio button para este estudiante en particular
            estado = request.POST.get(f'estado_{est_id}')
            presente = True if estado == 'presente' else False
            
            # Guardamos el registro en la base de datos
            RegistroAsistencia.objects.create(
                estudiante=estudiante,
                docente=request.user,
                presente=presente,
                justificado=False # Se puede actualizar luego si traen justificativo
            )
            
            # Si está ausente, disparamos la notificación al apoderado
            if not presente and hasattr(estudiante, 'apoderado') and estudiante.apoderado:
                MensajeComunicacion.objects.create(
                    remitente=request.user,
                    destinatario=estudiante.apoderado,
                    asunto=f"Aviso de inasistencia: {estudiante.nombre_completo}",
                    cuerpo_mensaje=(
                        f"Estimado apoderado,\n\n"
                        f"Le informamos que el estudiante {estudiante.nombre_completo} "
                        f"(RUT: {estudiante.rut_estudiante}) no se presentó a clases el día de hoy.\n\n"
                        f"Por favor, justifique su inasistencia a la brevedad.\n\n"
                        f"Saludos cordiales."
                    ),
                    tipo_comunicacion='academico' # Clasificamos la notificación
                )
        
        messages.success(request, "Lista de asistencia guardada y notificaciones enviadas correctamente.")
        return redirect('academico:home_docente')

    # Para la solicitud GET (cuando entra a la página) le pasamos los cursos
    cursos = Curso.objects.all() # O Curso.objects.filter(docente=request.user) si lo prefieres
    return render(request, 'academico/tomar_asistencia.html', {'cursos': cursos})
    