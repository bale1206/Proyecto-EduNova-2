import calendar as cal
from datetime import date

from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from comunicacion.services import mensajes_no_leidos
from usuarios.models import Usuario

from .forms import CarreraForm, AsignarCarreraForm, MatricularSeccionForm, CursoForm, EventoForm, JustificacionRetiroForm, ObservacionForm, ActualizarObservacionForm
from django.db.models import Case, When, Value, IntegerField, Count, Q
from .models import Asignatura, Asistencia, Carrera, Curso, Estudiante, Evento, JustificacionRetiro, ObservacionComportamiento, RegistroAsistencia, SesionClase, MarcaAsistencia, AvisoAsistencia
from django.http import JsonResponse
from comunicacion.models import MensajeComunicacion
from .notificaciones_asistencia import avisar_estudiante

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

    cursos = Curso.objects.filter(Q(docentes=request.user) | Q(docente_jefe=request.user)).distinct().order_by('asignatura', 'seccion')
    seccion_seleccionada = request.GET.get('seccion', '')
    if not seccion_seleccionada.isdecimal():
        seccion_seleccionada = ''
    # Nunca permitir consultar el calendario de un docente ajeno.
    if seccion_seleccionada and not cursos.filter(pk=seccion_seleccionada).exists():
        seccion_seleccionada = ''
    cursos_calendario = cursos.filter(pk=seccion_seleccionada) if seccion_seleccionada else cursos
    ahora = date.today()

    proxima_clase = (
        Evento.objects.filter(curso__in=cursos_calendario, tipo=Evento.Tipo.CLASE, fecha__gte=ahora)
        .order_by('fecha', 'hora_inicio')
        .first()
    )

    notificaciones = mensajes_no_leidos(request.user)[:8]
    total_no_leidos = mensajes_no_leidos(request.user).count()

    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    eventos_mes = Evento.objects.filter(curso__in=cursos_calendario, fecha__year=year, fecha__month=month)
    semanas = _construir_calendario(year, month, eventos_mes)

    contexto = {
        'cursos': cursos, 'seccion_seleccionada': seccion_seleccionada,
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

    observaciones = estudiante.observaciones.filter(confidencial=False).exclude(tipo='positiva').order_by('-fecha')[:10]

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
    carrera = request.user.carrera_dirigida
    if carrera is None:
        return render(request, 'academico/home_administrativo.html', {'sin_carrera': True})

    # Solo secciones explícitamente vinculadas al catálogo de la carrera.
    cursos = Curso.objects.filter(asignatura_catalogo__carreras=carrera).select_related(
        'docente_jefe', 'asignatura_catalogo').distinct().order_by('asignatura', 'seccion')
    seleccion = request.GET.get('seccion', '')
    if not seleccion.isdecimal() or not cursos.filter(pk=seleccion).exists():
        seleccion = ''
    visibles = cursos.filter(pk=seleccion) if seleccion else cursos
    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    eventos = Evento.objects.filter(curso__in=visibles, fecha__year=year, fecha__month=month)
    proximos = Evento.objects.filter(curso__in=cursos, fecha__gte=date.today()).select_related('curso').order_by('fecha','hora_inicio')[:8]
    form = EventoForm()
    form.fields['curso'].queryset = cursos
    form.fields['tipo'].choices = [(Evento.Tipo.REUNION, 'Reunión'), (Evento.Tipo.OTRO, 'Otro evento')]
    contexto = {
        'carrera': carrera, 'cursos': cursos, 'seccion_seleccionada': seleccion,
        'total_estudiantes': Estudiante.objects.filter(carrera=carrera).count(),
        'proximos_eventos': proximos, 'evento_form': form,
        'semanas': _construir_calendario(year, month, eventos),
        'mes_nombre': MESES_ES[month], 'anio': year, 'mes': month,
        'prev_year': prev_y, 'prev_month': prev_m,
        'next_year': next_y, 'next_month': next_m,
    }
    if request.headers.get('HX-Request'):
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/home_administrativo.html', contexto)


@login_required
def analitica_carrera(request):
    """Asistencia por carrera, asignatura y sección, sin mostrar otras carreras."""
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    carrera = request.user.carrera_dirigida
    if carrera is None:
        return render(request, 'academico/analitica_carrera.html', {'sin_carrera': True})
    asignaturas = Asignatura.objects.filter(carreras=carrera, activa=True).distinct().order_by('nombre')
    codigo = request.GET.get('asignatura', '')
    elegida = asignaturas.filter(pk=codigo).first() if codigo.isdecimal() else None
    if not elegida:
        elegida = asignaturas.first()
    disponibles = Curso.objects.filter(asignatura_catalogo=elegida).order_by('seccion') if elegida else Curso.objects.none()
    seccion_id = request.GET.get('seccion', '')
    if not seccion_id.isdecimal() or not disponibles.filter(pk=seccion_id).exists():
        seccion_id = ''
    visibles = disponibles.filter(pk=seccion_id) if seccion_id else disponibles
    marcas = MarcaAsistencia.objects.filter(sesion__seccion__in=visibles, estudiante__carrera=carrera)
    total = marcas.count()
    presentes = marcas.filter(presente=True).count()
    ausentes = total - presentes
    porcentaje = round(presentes * 100 / total, 1) if total else None
    detalle = []
    for sec in visibles:
        base = marcas.filter(sesion__seccion=sec)
        n = base.count()
        p = base.filter(presente=True).count()
        detalle.append({'seccion':sec, 'total':n, 'presentes':p, 'porcentaje':round(p*100/n,1) if n else None})
    return render(request, 'academico/analitica_carrera.html', {
        'carrera':carrera, 'asignaturas':asignaturas, 'asignatura_seleccionada':elegida,
        'secciones_disponibles':disponibles, 'seccion_seleccionada':seccion_id,
        'total_registros':total, 'presentes':presentes, 'ausentes':ausentes,
        'porcentaje':porcentaje, 'detalle':detalle,
    })


@login_required
def crear_carrera(request):
    raise PermissionDenied('Esta administración se realiza exclusivamente en Django Admin.')


@login_required
def asignar_carrera(request):
    raise PermissionDenied('Esta administración se realiza exclusivamente en Django Admin.')


@login_required
def matricular_seccion(request):
    raise PermissionDenied('Esta administración se realiza exclusivamente en Django Admin.')


@login_required
def crear_curso(request):
    raise PermissionDenied('Esta administración se realiza exclusivamente en Django Admin.')


@login_required
def crear_evento(request):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    if request.method == 'POST':
        form = EventoForm(request.POST)
        carrera = request.user.carrera_dirigida
        if not carrera:
            raise PermissionDenied('No tienes una carrera asignada.')
        form.fields['curso'].queryset = Curso.objects.filter(asignatura_catalogo__carreras=carrera).distinct()
        form.fields['tipo'].choices = [(Evento.Tipo.REUNION, 'Reunión'), (Evento.Tipo.OTRO, 'Otro evento')]
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
def lista_observaciones(request):
    """Lista de observaciones visible únicamente para personal autorizado."""
    if request.user.rol == Usuario.Rol.DOCENTE:
        observaciones = ObservacionComportamiento.objects.filter(docente=request.user)
    elif request.user.rol == Usuario.Rol.ADMINISTRATIVO:
        if not request.user.carrera_dirigida_id:
            raise PermissionDenied('No tienes una carrera asignada.')
        observaciones = ObservacionComportamiento.objects.filter(
            estudiantes__carrera_id=request.user.carrera_dirigida_id
        ).distinct()
    else:
        raise PermissionDenied('No tienes acceso a las observaciones.')

    observaciones = observaciones.prefetch_related('estudiantes').order_by('-fecha', '-pk')[:100]
    return render(request, 'academico/lista_observaciones.html', {
        'observaciones': observaciones,
    })

@login_required
def editar_observacion(request, pk):
    registros = ObservacionComportamiento.objects.all()
    if request.user.rol == Usuario.Rol.ADMINISTRATIVO:
        if not request.user.carrera_dirigida_id:
            raise PermissionDenied('No tienes una carrera asignada.')
        registros = registros.filter(estudiantes__carrera_id=request.user.carrera_dirigida_id).distinct()
    observacion = get_object_or_404(registros, pk=pk)
    
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

@login_required
def cargar_estudiantes(request):
    _requerir_rol(request, Usuario.Rol.DOCENTE)
    seccion = get_object_or_404(Curso.objects.filter(Q(docentes=request.user) | Q(docente_jefe=request.user)).distinct(), pk=request.GET.get('curso_id'))
    alumnado = Estudiante.objects.filter(secciones=seccion).distinct().order_by('nombre_completo')
    if not alumnado.exists():
        alumnado = Estudiante.objects.filter(curso=seccion).order_by('nombre_completo')
    sesion = SesionClase.objects.filter(seccion=seccion, fecha=timezone.localdate()).first()
    previas = dict(sesion.marcas.values_list('estudiante_id', 'presente')) if sesion else {}
    return JsonResponse([{'id':e.id, 'nombre_completo':e.nombre_completo, 'presente':previas.get(e.id)} for e in alumnado])


@login_required
@require_http_methods(['GET','POST'])
def tomar_asistencia(request):
    _requerir_rol(request, Usuario.Rol.DOCENTE)
    secciones = Curso.objects.filter(Q(docentes=request.user) | Q(docente_jefe=request.user)).distinct().order_by('asignatura', 'seccion')
    if request.method == 'POST':
        seccion = get_object_or_404(secciones, pk=request.POST.get('curso'))
        alumnado = Estudiante.objects.filter(secciones=seccion).distinct()
        if not alumnado.exists():
            alumnado = Estudiante.objects.filter(curso=seccion)
        alumnos = list(alumnado.select_related('usuario'))
        if not alumnos:
            messages.error(request, 'Esta sección no tiene estudiantes matriculados.')
            return redirect('academico:tomar_asistencia')
        estados = {}
        for alumno in alumnos:
            valor = request.POST.get(f'estado_{alumno.pk}')
            if valor not in ('presente','ausente'):
                messages.error(request, 'Debes marcar presente o ausente para cada estudiante.')
                return redirect('academico:tomar_asistencia')
            estados[alumno.pk] = valor == 'presente'
        with transaction.atomic():
            sesion, _ = SesionClase.objects.get_or_create(
                seccion=seccion, fecha=timezone.localdate(),
                defaults={'docente':request.user})
            if sesion.docente_id != request.user.pk:
                raise PermissionDenied('La asistencia del día pertenece a otro docente.')
            cambios = []
            for alumno in alumnos:
                anterior = MarcaAsistencia.objects.filter(sesion=sesion, estudiante=alumno).values_list('presente', flat=True).first()
                presente = estados[alumno.pk]
                marca, _ = MarcaAsistencia.objects.update_or_create(
                    sesion=sesion, estudiante=alumno, defaults={'presente':presente})
                if anterior is None or anterior != presente:
                    if alumno.usuario_id and alumno.usuario.rol == Usuario.Rol.ESTUDIANTE:
                        texto = (f'¡Qué bueno que asististe a {seccion.asignatura}, sigue así!'
                                 if presente else
                                 f'No te vimos hoy en {seccion.asignatura}, esperamos verte pronto.')
                        aviso = AvisoAsistencia.objects.create(destinatario_id=alumno.usuario_id, marca=marca, texto=texto)
                        cambios.append((alumno.usuario_id, aviso.pk, texto))
            # Publicar tras el commit: el aviso queda guardado aun si no hay WebSocket conectado.
            transaction.on_commit(lambda cambios=cambios: [avisar_estudiante(uid, aid, texto) for uid, aid, texto in cambios])
        messages.success(request, 'Asistencia del día guardada. Puedes corregirla durante el mismo día.')
        return redirect('academico:tomar_asistencia')
    return render(request, 'academico/tomar_asistencia.html', {'cursos':secciones, 'fecha_hoy':timezone.localdate()})


@login_required
def home_estudiante(request):
    """Portal privado del estudiante; no depende del vínculo con apoderados."""
    from .models import TareaEstudio
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    perfil = Estudiante.objects.filter(usuario=request.user).select_related('carrera', 'curso').first()
    tareas = TareaEstudio.objects.filter(estudiante=request.user)
    secciones = Curso.objects.filter(matriculados=perfil).order_by('asignatura', 'seccion') if perfil else Curso.objects.none()
    # Compatibilidad con registros antiguos, sin duplicar secciones.
    if perfil and not secciones.exists() and perfil.curso_id:
        secciones = Curso.objects.filter(pk=perfil.curso_id)
    seccion_seleccionada = request.GET.get('seccion', '')
    if not seccion_seleccionada.isdecimal():
        seccion_seleccionada = ''
    if seccion_seleccionada and not secciones.filter(pk=seccion_seleccionada).exists():
        seccion_seleccionada = ''
    visibles = secciones.filter(pk=seccion_seleccionada) if seccion_seleccionada else secciones
    eventos = Evento.objects.filter(curso__in=visibles).order_by('fecha', 'hora_inicio')
    today = date.today()
    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    semanas = _construir_calendario(year, month, eventos.filter(fecha__year=year, fecha__month=month))
    contexto = {
        'perfil': perfil, 'secciones': secciones, 'seccion_seleccionada': seccion_seleccionada, 'tareas': tareas, 'pendientes': tareas.filter(completada=False),
        'eventos_proximos': eventos.filter(fecha__gte=today)[:6],
        'mes_nombre': MESES_ES[month], 'anio': year, 'mes': month,
        'semanas': semanas, 'prev_year': prev_y, 'prev_month': prev_m,
        'next_year': next_y, 'next_month': next_m,
        'total_no_leidos': mensajes_no_leidos(request.user).count(),
        'avisos_asistencia': AvisoAsistencia.objects.filter(destinatario=request.user)[:5],
    }
    # HTMX sustituye solo #calendario-mensual: nunca enviar toda la página.
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/home_estudiante.html', contexto)


@login_required
def crear_tarea_estudiante(request):
    from datetime import datetime
    from .models import TareaEstudio
    from django.views.decorators.http import require_POST
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    if request.method != 'POST':
        raise PermissionDenied('Acción no permitida.')
    titulo = request.POST.get('titulo', '').strip()
    fecha_raw = request.POST.get('fecha_limite', '').strip()
    if not titulo or len(titulo) > 160:
        messages.error(request, 'Ingresa un título de hasta 160 caracteres.')
    else:
        try:
            fecha = date.fromisoformat(fecha_raw) if fecha_raw else None
        except ValueError:
            messages.error(request, 'La fecha indicada no es válida.')
        else:
            TareaEstudio.objects.create(estudiante=request.user, titulo=titulo, fecha_limite=fecha)
            messages.success(request, 'Tarea añadida a tu planificación.')
    return redirect('academico:home_estudiante')


@login_required
def alternar_tarea_estudiante(request, tarea_id):
    from .models import TareaEstudio
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    if request.method != 'POST':
        raise PermissionDenied('Acción no permitida.')
    tarea = get_object_or_404(TareaEstudio, pk=tarea_id, estudiante=request.user)
    tarea.completada = not tarea.completada
    tarea.save(update_fields=['completada'])
    return redirect('academico:home_estudiante')


@login_required
def eliminar_tarea_estudiante(request, tarea_id):
    from .models import TareaEstudio
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    if request.method != 'POST':
        raise PermissionDenied('Acción no permitida.')
    get_object_or_404(TareaEstudio, pk=tarea_id, estudiante=request.user).delete()
    return redirect('academico:home_estudiante')
