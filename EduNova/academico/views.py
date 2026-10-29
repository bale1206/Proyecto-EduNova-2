import calendar as cal
from types import SimpleNamespace
from datetime import date

from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from comunicacion.services import mensajes_no_leidos
from usuarios.models import Usuario

from .forms import ActividadAdministrativaForm, CrearSeccionForm, CarreraForm, AsignarCarreraForm, MatricularSeccionForm, CursoForm, EventoForm, ObservacionForm, ActualizarObservacionForm
from django.db.models import Case, When, Value, IntegerField, Count, Q
from .models import TareaEstudio, Asignatura, Carrera, Curso, Estudiante, Evento, ObservacionComportamiento, RegistroAsistencia, SesionClase, MarcaAsistencia, AvisoAsistencia
from django.http import JsonResponse
from comunicacion.models import MensajeComunicacion
from .notificaciones_asistencia import avisar_estudiante
from .analitica import resumir_asistencia
from .calendario_clases import clases_por_dia, secciones_eligibles

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
    return _portal_planificacion(request)


@login_required
def home_administrativo(request, evento_form=None):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    return _portal_planificacion(request)


@login_required
def analitica_carrera(request):
    """Filtros encadenados: carrera, asignatura de su malla y sección."""
    if not request.user.is_superuser:
        _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    carreras = Carrera.objects.all().order_by('escuela', 'nombre')
    carrera_id = request.GET.get('carrera')
    historico = carrera_id == 'historico'
    if carrera_id is None:
        carrera = carreras.filter(pk=request.user.carrera_dirigida_id).first() or carreras.first()
    else:
        carrera = carreras.filter(pk=carrera_id).first() if carrera_id.isdecimal() else None
    asignaturas = Asignatura.objects.filter(carreras=carrera).distinct().order_by('nombre', 'codigo') if carrera else Asignatura.objects.none()
    codigo = request.GET.get('asignatura', '')
    elegida = asignaturas.filter(pk=codigo).first() if codigo.isdecimal() else None
    if not elegida:
        elegida = asignaturas.first()
    disponibles = Curso.objects.filter(asignatura_catalogo=elegida).order_by('seccion') if elegida else Curso.objects.none()
    if historico:
        # Estas secciones no pueden asociarse a una carrera sin inventar datos.
        # Se consultan en una selección explícita, independiente de las mallas.
        nombres = Curso.objects.filter(asignatura_catalogo__isnull=True).values_list('asignatura', flat=True).distinct().order_by('asignatura')
        asignaturas = [SimpleNamespace(pk=nombre, nombre=nombre) for nombre in nombres]
        elegida = next((asignatura for asignatura in asignaturas if asignatura.pk == codigo), None)
        if elegida is None and asignaturas:
            elegida = asignaturas[0]
        disponibles = Curso.objects.filter(asignatura_catalogo__isnull=True, asignatura=elegida.pk).order_by('seccion') if elegida else Curso.objects.none()
    seccion_id = request.GET.get('seccion', '')
    if not seccion_id.isdecimal() or not disponibles.filter(pk=seccion_id).exists():
        seccion_id = ''
    visibles = disponibles.filter(pk=seccion_id) if seccion_id else disponibles
    resumen = resumir_asistencia(visibles, carrera)
    return render(request, 'academico/analitica_carrera.html', {
        'carreras':carreras, 'carrera':carrera, 'asignaturas':asignaturas, 'asignatura_seleccionada':elegida,
        'historico': historico,
        'secciones_disponibles':disponibles, 'seccion_seleccionada':seccion_id,
        **resumen,
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
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    form = CrearSeccionForm(request.POST if request.method == 'POST' else None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                seccion = form.save()
            messages.success(request, f'Sección {seccion.seccion} creada correctamente.')
            return redirect('academico:home_administrativo')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'academico/crear_seccion.html', {'form': form}, status=200)


@login_required
def opciones_seccion(request):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    carreras = Carrera.objects.all()
    carrera_id = request.GET.get('carrera', '')
    from django.http import Http404
    if not carrera_id.isdecimal():
        raise Http404
    carrera = get_object_or_404(carreras, pk=carrera_id)
    asignaturas = Asignatura.objects.filter(carreras=carrera, activa=True).distinct().order_by('nombre', 'codigo')
    datos = {'asignaturas': [{'id': a.pk, 'nombre': str(a)} for a in asignaturas]}
    asignatura_id = request.GET.get('asignatura')
    if asignatura_id:
        if not asignatura_id.isdecimal():
            raise Http404
        asignatura = get_object_or_404(asignaturas, pk=asignatura_id)
        from .secciones import siguiente_numero, prefijo_asignatura
        try:
            numero = siguiente_numero(Curso, asignatura.nombre)
            datos.update(numero=f'{numero:03d}', prefijo=prefijo_asignatura(asignatura.nombre))
        except ValidationError as exc:
            return JsonResponse({'error': '; '.join(exc.messages)}, status=400)
    return JsonResponse(datos)


@login_required
@require_http_methods(['POST'])
def crear_evento(request):
    """Eventos compartidos: docentes por sección, directores por sección o carrera."""
    if request.user.rol not in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
        raise PermissionDenied('Solo docentes y directores pueden publicar actividades.')
    from datetime import time
    titulo = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    tipo = request.POST.get('tipo', Evento.Tipo.OTRO)
    seccion_id = request.POST.get('seccion', '')
    alcance = request.POST.get('alcance', 'seccion')
    if not titulo or len(titulo) > 150 or tipo not in Evento.Tipo.values:
        messages.error(request, 'Revisa el título y el tipo de evento.')
        return redirect(_portal_url(request.user))
    try:
        fecha = date.fromisoformat(request.POST.get('fecha', ''))
        hora = time.fromisoformat(request.POST['hora_inicio']) if request.POST.get('hora_inicio') else None
        fin = time.fromisoformat(request.POST['hora_fin']) if request.POST.get('hora_fin') else None
    except ValueError:
        messages.error(request, 'Fecha u hora no válida.')
        return redirect(_portal_url(request.user))
    if hora and fin and fin <= hora:
        messages.error(request, 'La hora de término debe ser posterior a la de inicio.')
        return redirect(_portal_url(request.user))
    carrera = None
    seccion = None
    if alcance == 'carrera' and request.user.rol == Usuario.Rol.ADMINISTRATIVO:
        carrera = request.user.carrera_dirigida
        if carrera is None:
            raise PermissionDenied('No tienes una carrera asignada.')
    else:
        if not seccion_id.isdecimal():
            raise PermissionDenied('Selecciona una sección válida.')
        seccion = get_object_or_404(_secciones_planificador(request.user), pk=seccion_id)
    Evento.objects.create(curso=seccion, carrera=carrera, creado_por=request.user,
                          tipo=tipo, titulo=titulo, descripcion=descripcion,
                          fecha=fecha, hora_inicio=hora, hora_fin=fin)
    messages.success(request, 'Evento publicado en los calendarios correspondientes.')
    return redirect(_portal_url(request.user))


@login_required
def crear_observacion(request):
    _requerir_rol(request, Usuario.Rol.DOCENTE)
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

def _observaciones_autorizadas(usuario):
    registros = ObservacionComportamiento.objects.all()
    if usuario.is_superuser:
        return registros
    if usuario.rol == Usuario.Rol.DOCENTE:
        return registros.filter(docente=usuario)
    if usuario.rol == Usuario.Rol.ADMINISTRATIVO and usuario.carrera_dirigida_id:
        carrera_id = usuario.carrera_dirigida_id
        return registros.filter(
            Q(estudiantes__carrera_id=carrera_id) | Q(curso__asignatura_catalogo__carreras__pk=carrera_id)
        ).exclude(estudiantes__in=Estudiante.objects.exclude(carrera_id=carrera_id)).distinct()
    raise PermissionDenied('No tienes acceso a estas observaciones.')


@login_required
def lista_observaciones(request):
    observaciones = _observaciones_autorizadas(request.user).exclude(estado='RESUELTA').exclude(tipo_observacion='POSITIVA')
    observaciones = observaciones.prefetch_related('estudiantes').order_by('-fecha_actualizacion', '-pk')[:100]
    return render(request, 'academico/lista_observaciones.html', {'observaciones': observaciones})


@login_required
def actualizar_observacion(request, pk):
    observacion = get_object_or_404(_observaciones_autorizadas(request.user), pk=pk)
    form = ActualizarObservacionForm(request.POST if request.method == 'POST' else None, instance=observacion)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obs = form.save(commit=False)
            obs.administrativo = request.user
            obs.save()
            notificados = 0
            sin_cuenta = []
            if form.cleaned_data.get('notificar_apoderado'):
                for estudiante in obs.estudiantes.select_related('usuario'):
                    destinatario = estudiante.usuario
                    if not destinatario or destinatario.rol != Usuario.Rol.ESTUDIANTE:
                        sin_cuenta.append(estudiante.nombre_completo)
                        continue
                    MensajeComunicacion.objects.create(
                        remitente=request.user, destinatario=destinatario,
                        asunto=f'Actualización de observación: {obs.asunto}'[:150],
                        cuerpo_mensaje=(f'Hola {estudiante.nombre_completo},\n\n'
                            f'Asunto: {obs.asunto}\nTipo: {obs.get_tipo_observacion_display()}\n'
                            f'Estado: {obs.get_estado_display()}\n'
                            f'Resolución administrativa:\n{obs.resolucion or "Sin resolución registrada."}'),
                        tipo_comunicacion=MensajeComunicacion.TipoComunicacion.DISCIPLINARIO,
                    )
                    notificados += 1
        messages.success(request, f'Observación actualizada. Estudiantes notificados: {notificados}.' if form.cleaned_data.get('notificar_apoderado') else 'Observación actualizada correctamente.')
        if sin_cuenta:
            messages.warning(request, 'No se pudo notificar porque no tienen una cuenta con rol estudiante vinculada: ' + ', '.join(sin_cuenta))
        return redirect('academico:lista_observaciones')
    return render(request, 'academico/actualizar_observacion.html', {'form': form, 'observacion': observacion})


# Compatibilidad con referencias internas a la vista anterior.
editar_observacion = actualizar_observacion


def _secciones_asistencia(usuario):
    if usuario.is_superuser:
        return Curso.objects.all()
    if usuario.rol == Usuario.Rol.DOCENTE:
        return Curso.objects.filter(Q(docentes=usuario) | Q(docente_jefe=usuario)).distinct()
    if usuario.rol == Usuario.Rol.ADMINISTRATIVO and usuario.carrera_dirigida_id:
        return Curso.objects.filter(asignatura_catalogo__carreras__pk=usuario.carrera_dirigida_id).distinct()
    raise PermissionDenied('No tienes acceso al registro de asistencia.')


@login_required
def cargar_estudiantes(request):
    curso_id = request.GET.get('curso_id', '')
    from django.http import Http404
    if not curso_id.isdecimal():
        raise Http404
    seccion = get_object_or_404(_secciones_asistencia(request.user), pk=curso_id)
    alumnado = Estudiante.objects.filter(secciones=seccion).distinct().order_by('nombre_completo')
    if not alumnado.exists():
        alumnado = Estudiante.objects.filter(curso=seccion).order_by('nombre_completo')
    sesion = SesionClase.objects.filter(seccion=seccion, fecha=timezone.localdate()).first()
    previas = dict(sesion.marcas.values_list('estudiante_id', 'presente')) if sesion else {}
    return JsonResponse([{'id':e.id, 'rut':e.rut_estudiante, 'nombre_completo':e.nombre_completo, 'presente':previas.get(e.id), 'fecha_registro':timezone.localtime(sesion.actualizada_en).strftime('%H-%M--%d/%m/%Y') if sesion else ''} for e in alumnado], safe=False)


@login_required
@require_http_methods(['GET','POST'])
def tomar_asistencia(request):
    secciones = _secciones_asistencia(request.user).order_by('asignatura', 'seccion')
    if request.method == 'POST':
        curso_id = request.POST.get('curso', '')
        from django.http import Http404
        if not curso_id.isdecimal():
            raise Http404
        seccion = get_object_or_404(secciones, pk=curso_id)
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
            sesion, _ = SesionClase.objects.select_for_update().get_or_create(
                seccion=seccion, fecha=timezone.localdate(),
                defaults={'docente':request.user})
            if sesion.docente_id != request.user.pk and not request.user.is_superuser and request.user.rol != Usuario.Rol.ADMINISTRATIVO:
                raise PermissionDenied('La asistencia del día pertenece a otro docente.')
            sesion.save(update_fields=["actualizada_en"])
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
                # Mantener el registro histórico asociado al formulario de Django Admin.
                historicos = RegistroAsistencia.objects.filter(estudiante=alumno, seccion=seccion, fecha__date=timezone.localdate())
                historico = historicos.order_by('-fecha').first()
                if historico:
                    historico.presente = presente
                    historico.save(update_fields=['presente'])
                else:
                    RegistroAsistencia.objects.create(estudiante=alumno, seccion=seccion, docente=request.user, presente=presente)
            # Publicar tras el commit: el aviso queda guardado aun si no hay WebSocket conectado.
            transaction.on_commit(lambda cambios=cambios: [avisar_estudiante(uid, aid, texto) for uid, aid, texto in cambios])
        messages.success(request, 'Asistencia guardada: ' + timezone.localtime(sesion.actualizada_en).strftime('%H-%M--%d/%m/%Y') + '. Puedes corregirla durante el mismo día.')
        return redirect('academico:tomar_asistencia')
    return render(request, 'academico/tomar_asistencia.html', {'cursos':secciones, 'fecha_hoy':timezone.localdate()})


def _portal_url(user):
    return 'academico:home_docente' if user.rol == Usuario.Rol.DOCENTE else 'academico:home_administrativo'


def _secciones_planificador(user):
    if user.rol == Usuario.Rol.DOCENTE:
        return Curso.objects.filter(Q(docentes=user) | Q(docente_jefe=user)).distinct()
    if user.rol == Usuario.Rol.ADMINISTRATIVO and user.carrera_dirigida_id:
        return Curso.objects.filter(asignatura_catalogo__carreras__pk=user.carrera_dirigida_id).distinct()
    return Curso.objects.none()


def _portal_planificacion(request):
    """Mismo calendario para docentes y directores; tareas privadas y eventos públicos."""
    user = request.user
    secciones = _secciones_planificador(user).order_by('asignatura', 'seccion')
    seleccion = request.GET.get('seccion', '')
    if not seleccion.isdecimal() or not secciones.filter(pk=seleccion).exists():
        seleccion = ''
    visibles = secciones.filter(pk=seleccion) if seleccion else secciones
    eventos = Evento.objects.filter(curso__in=visibles)
    if user.rol == Usuario.Rol.ADMINISTRATIVO and user.carrera_dirigida_id:
        eventos = Evento.objects.filter(Q(curso__in=visibles) | Q(carrera_id=user.carrera_dirigida_id))
    elif user.rol == Usuario.Rol.DOCENTE:
        # Eventos de carrera también son visibles para el equipo de sus secciones.
        carreras = Carrera.objects.filter(asignaturas__secciones__in=secciones).distinct()
        eventos = Evento.objects.filter(Q(curso__in=visibles) | Q(carrera__in=carreras))
    eventos = eventos.distinct().order_by('fecha', 'hora_inicio')
    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    semanas = _construir_calendario(year, month, eventos.filter(fecha__year=year, fecha__month=month))
    clases_mes = clases_por_dia(list(visibles), year, month, hoy=timezone.localdate())
    for semana in semanas:
        for dia in semana:
            dia['clases'] = clases_mes.get(dia['numero'], []) if dia['numero'] else []
    from .programacion_tareas import fechas_tarea
    import calendar
    inicio, final = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    tareas = TareaEstudio.objects.filter(estudiante=user).select_related('seccion')
    ocurrencias = {}
    for tarea in tareas:
        if seleccion and str(tarea.seccion_id) != seleccion:
            continue
        for fecha in fechas_tarea(tarea, inicio, final):
            ocurrencias.setdefault(fecha.day, []).append(tarea)
    for semana in semanas:
        for dia in semana:
            dia['tareas'] = ocurrencias.get(dia['numero'], []) if dia['numero'] else []
    contexto = {'secciones': secciones, 'seccion_seleccionada': seleccion,
        'semanas': semanas, 'mes_nombre': MESES_ES[month], 'anio': year, 'mes': month,
        'prev_year': prev_y, 'prev_month': prev_m, 'next_year': next_y, 'next_month': next_m,
        'tareas': tareas, 'proximos_eventos': eventos.filter(fecha__gte=timezone.localdate())[:8],
        'es_director': user.rol == Usuario.Rol.ADMINISTRATIVO,
        'recordatorios_no_leidos': user.recordatorios_tareas.filter(leido=False).count(),
        'recordatorios_recientes': user.recordatorios_tareas.filter(leido=False)[:8],
        'tarea_para_configurar': tareas.filter(pk=request.GET.get('configurar_tarea')).first() if request.GET.get('configurar_tarea', '').isdecimal() else None,
    }
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/planificacion_equipo.html', contexto)


@login_required
@require_http_methods(['POST'])
def crear_tarea_equipo(request):
    from datetime import time
    import re
    if request.user.rol not in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
        raise PermissionDenied
    titulo = request.POST.get('titulo', '').strip()
    if not titulo or len(titulo) > 160:
        messages.error(request, 'Título inválido.')
        return redirect(_portal_url(request.user))
    seccion = None
    seccion_id = request.POST.get('seccion', '')
    if seccion_id:
        if not seccion_id.isdecimal():
            raise PermissionDenied
        seccion = get_object_or_404(_secciones_planificador(request.user), pk=seccion_id)
    try:
        fecha = date.fromisoformat(request.POST.get('fecha_limite', ''))
        hora = time.fromisoformat(request.POST.get('hora_inicio', ''))
        minutos = int(request.POST.get('minutos_antes', '15'))
    except (ValueError, TypeError):
        messages.error(request, 'Fecha, hora o recordatorio inválido.')
        return redirect(_portal_url(request.user))
    repeticion = request.POST.get('repeticion', 'ninguna')
    prioridad = request.POST.get('prioridad', 'media')
    color = request.POST.get('color', '#4C849D').upper()
    if repeticion not in ('ninguna', 'diaria', 'semanal', 'mensual') or prioridad not in ('alta', 'media', 'baja') or minutos not in (0,5,10,15,30,60):
        raise PermissionDenied('Opción no válida.')
    if not re.fullmatch(r'#[0-9A-F]{6}', color):
        color = '#4C849D'
    tarea = TareaEstudio.objects.create(estudiante=request.user, seccion=seccion, titulo=titulo,
        fecha_limite=fecha, hora_inicio=hora, repeticion=repeticion, prioridad=prioridad,
        minutos_antes=minutos, color=color)
    return redirect(f"{reverse(_portal_url(request.user))}?configurar_tarea={tarea.pk}#configurar-recordatorio")


@login_required
@require_http_methods(['POST'])
def tarea_equipo_accion(request, tarea_id, accion):
    if request.user.rol not in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
        raise PermissionDenied
    tarea = get_object_or_404(TareaEstudio, pk=tarea_id, estudiante=request.user)
    if accion == 'alternar':
        tarea.completada = not tarea.completada
        tarea.save(update_fields=['completada'])
    elif accion == 'eliminar':
        tarea.delete()
    elif accion == 'recordatorio':
        activar = request.POST.get('activar')
        if activar not in ('si', 'no'):
            raise PermissionDenied
        tarea.recordatorios_activos = activar == 'si'
        tarea.save(update_fields=['recordatorios_activos'])
    else:
        raise PermissionDenied
    return redirect(_portal_url(request.user))


@login_required
@require_http_methods(['POST'])
def recordatorios_equipo(request):
    if request.user.rol not in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
        raise PermissionDenied
    request.user.recordatorios_tareas.filter(leido=False).update(leido=True)
    return redirect(_portal_url(request.user))


@login_required
def home_estudiante(request):
    """Portal privado del estudiante; no depende del vínculo con apoderados."""
    from .models import TareaEstudio
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    perfil = Estudiante.objects.filter(usuario=request.user).select_related('carrera', 'curso').first()
    tareas = TareaEstudio.objects.filter(estudiante=request.user).select_related('seccion')
    # La matrícula M2M es la fuente de verdad: NO usar perfil.curso como
    # alternativa, porque podría apuntar a una sección histórica distinta.
    secciones = (Curso.objects.filter(matriculados=perfil)
                .select_related('asignatura_catalogo', 'periodo_academico')
                .prefetch_related('horarios')
                .order_by('asignatura_catalogo__nombre', 'codigo_institucional', 'seccion')
                if perfil else Curso.objects.none())
    seccion_seleccionada = request.GET.get('seccion', '')
    if not seccion_seleccionada.isdecimal():
        seccion_seleccionada = ''
    if seccion_seleccionada and not secciones.filter(pk=seccion_seleccionada).exists():
        seccion_seleccionada = ''
    visibles = secciones.filter(pk=seccion_seleccionada) if seccion_seleccionada else secciones
    # Eventos de una sección solo al filtrarla; los avisos generales de
    # carrera se muestran cuando se visualizan todas las asignaturas.
    if perfil:
        filtro_eventos = Q(curso__in=visibles)
        if not seccion_seleccionada and perfil.carrera_id:
            filtro_eventos |= Q(carrera_id=perfil.carrera_id, curso__isnull=True)
        eventos = Evento.objects.filter(filtro_eventos).distinct().order_by('fecha', 'hora_inicio')
    else:
        eventos = Evento.objects.none()
    today = date.today()
    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    semanas = _construir_calendario(year, month, eventos.filter(fecha__year=year, fecha__month=month))
    tareas_mes = {}
    from .programacion_tareas import fechas_tarea
    import calendar
    ultimo_dia = calendar.monthrange(year, month)[1]
    desde, hasta = date(year, month, 1), date(year, month, ultimo_dia)
    for tarea in tareas:
        if seccion_seleccionada and str(tarea.seccion_id) != seccion_seleccionada:
            continue
        for ocurrencia in fechas_tarea(tarea, desde, hasta):
            tareas_mes.setdefault(ocurrencia.day, []).append(tarea)
    # Incorporar las clases recurrentes desde las secciones realmente matriculadas.
    # Antes solo se generaban eventos y tareas: por eso el calendario mostraba
    # «Sin actividades» aunque la sección tuviera horarios en Supabase.
    clases_mes = clases_por_dia(visibles, year, month, hoy=timezone.localdate())
    for semana in semanas:
        for dia in semana:
            numero = dia['numero']
            dia['clases'] = clases_mes.get(numero, []) if numero else []
            dia['tareas'] = tareas_mes.get(numero, []) if numero else []
    contexto = {
        'horarios_sin_cargar': sum(not bool(sec.horarios.all()) for sec in secciones),
        'perfil': perfil, 'secciones': secciones, 'seccion_seleccionada': seccion_seleccionada, 'tareas': tareas, 'pendientes': tareas.filter(completada=False),
        'eventos_proximos': eventos.filter(fecha__gte=today)[:6],
        'mes_nombre': MESES_ES[month], 'anio': year, 'mes': month,
        'semanas': semanas, 'prev_year': prev_y, 'prev_month': prev_m,
        'next_year': next_y, 'next_month': next_m,
        'total_no_leidos': mensajes_no_leidos(request.user).count(),
        'avisos_asistencia': AvisoAsistencia.objects.filter(destinatario=request.user)[:5],
        'recordatorios_no_leidos': request.user.recordatorios_tareas.filter(leido=False).count(),
        'recordatorios_recientes': request.user.recordatorios_tareas.filter(leido=False)[:6],
        'tarea_para_configurar': tareas.filter(pk=request.GET.get('configurar_tarea', '')).first() if request.GET.get('configurar_tarea', '').isdecimal() else None,
    }
    # HTMX sustituye solo #calendario-mensual: nunca enviar toda la página.
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/home_estudiante.html', contexto)


@login_required
@require_http_methods(['GET', 'POST'])
def ajustar_secciones_estudiante(request):
    """Permite corregir una matrícula vieja sin manipular Supabase a mano."""
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    perfil = Estudiante.objects.filter(usuario=request.user).select_related('carrera').first()
    if not perfil or not perfil.carrera_id or not perfil.modalidad:
        messages.error(request, 'Completa tu carrera y modalidad desde Django Admin antes de elegir secciones.')
        return redirect('academico:home_estudiante')
    opciones = secciones_eligibles(perfil)
    if request.method == 'POST':
        raw = request.POST.getlist('secciones')
        if not raw or len(set(raw)) != len(raw) or any(not x.isdecimal() for x in raw):
            messages.error(request, 'Selecciona al menos una sección válida, sin duplicados.')
            return redirect('academico:ajustar_secciones_estudiante')
        elegidas = list(opciones.filter(pk__in=[int(x) for x in raw]))
        if len(elegidas) != len(raw):
            messages.error(request, 'Una sección no pertenece a tu carrera, modalidad o período actual.')
            return redirect('academico:ajustar_secciones_estudiante')
        codigos_asignatura = [sec.asignatura_catalogo_id for sec in elegidas]
        if len(set(codigos_asignatura)) != len(codigos_asignatura):
            messages.error(request, 'Solo puedes seleccionar una sección por asignatura.')
            return redirect('academico:ajustar_secciones_estudiante')
        with transaction.atomic():
            perfil = Estudiante.objects.select_for_update().get(pk=perfil.pk, usuario=request.user)
            perfil.secciones.set(elegidas)
            # Campo escolar heredado: solo se conserva para compatibilidad.
            perfil.curso = elegidas[0]
            perfil.save(update_fields=['curso'])
        messages.success(request, 'Tus secciones y horarios quedaron sincronizados con el calendario.')
        return redirect('academico:home_estudiante')

    inscritas = set(perfil.secciones.values_list('id', flat=True))
    agrupadas = {}
    for sec in opciones:
        clave = sec.asignatura_catalogo_id
        if clave not in agrupadas:
            agrupadas[clave] = {'asignatura': sec.asignatura_catalogo, 'secciones': []}
        sec.seleccionada = sec.pk in inscritas
        agrupadas[clave]['secciones'].append(sec)
    return render(request, 'academico/ajustar_secciones_estudiante.html', {
        'perfil': perfil, 'grupos': list(agrupadas.values()),
        'secciones_actuales': perfil.secciones.select_related('asignatura_catalogo').all(),
    })


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
    hora_raw = request.POST.get('hora_inicio', '').strip()
    if not titulo or len(titulo) > 160:
        messages.error(request, 'Ingresa un título de hasta 160 caracteres.')
    else:
        try:
            fecha = date.fromisoformat(fecha_raw) if fecha_raw else None
        except ValueError:
            messages.error(request, 'La fecha indicada no es válida.')
        else:
            from datetime import time
            try:
                hora = time.fromisoformat(hora_raw)
            except (ValueError, TypeError):
                messages.error(request, 'Selecciona una hora válida para la tarea.')
                return redirect('academico:home_estudiante')
            if fecha is None:
                messages.error(request, 'Selecciona la fecha de inicio de la tarea.')
                return redirect('academico:home_estudiante')
            repeticion = request.POST.get('repeticion', 'ninguna')
            if repeticion not in ('ninguna','diaria','semanal','mensual'):
                messages.error(request, 'La repetición seleccionada no es válida.')
                return redirect('academico:home_estudiante')
            try:
                minutos_antes = int(request.POST.get('minutos_antes', '15'))
            except ValueError:
                minutos_antes = -1
            if minutos_antes not in (0,5,10,15,30,60):
                messages.error(request, 'La antelación debe ser 0, 5, 10, 15, 30 o 60 minutos.')
                return redirect('academico:home_estudiante')
            import re
            from .models import Curso
            seccion_id = request.POST.get('seccion', '')
            if not seccion_id.isdecimal():
                messages.error(request, 'Selecciona una asignatura matriculada.')
                return redirect('academico:home_estudiante')
            perfil = Estudiante.objects.filter(usuario=request.user).first()
            opciones = Curso.objects.filter(matriculados=perfil) if perfil else Curso.objects.none()
            if perfil and not opciones.exists() and perfil.curso_id:
                opciones = Curso.objects.filter(pk=perfil.curso_id)
            seccion = opciones.filter(pk=seccion_id).first()
            if seccion is None:
                raise PermissionDenied('La asignatura no pertenece a tu matrícula.')
            color = request.POST.get('color', '#4C849D').upper()
            if not re.fullmatch(r'#[0-9A-F]{6}', color):
                color = '#4C849D'
            prioridad = request.POST.get('prioridad', 'media')
            if prioridad not in ('alta', 'media', 'baja'):
                prioridad = 'media'
            tarea = TareaEstudio.objects.create(estudiante=request.user, titulo=titulo, fecha_limite=fecha,
                seccion=seccion, color=color, prioridad=prioridad, hora_inicio=hora,
                repeticion=repeticion, minutos_antes=minutos_antes)
            messages.success(request, 'Tarea creada. Decide si deseas recordatorios.')
            return redirect(f"{reverse('academico:home_estudiante')}?configurar_tarea={tarea.pk}#configurar-recordatorio")
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


@login_required
@require_http_methods(['POST'])
def configurar_recordatorio(request, tarea_id):
    from .models import TareaEstudio
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    tarea = get_object_or_404(TareaEstudio, pk=tarea_id, estudiante=request.user)
    decision = request.POST.get('activar')
    if decision not in ('si', 'no'):
        raise PermissionDenied('Selecciona Sí o No.')
    if decision == 'si' and (not tarea.fecha_limite or not tarea.hora_inicio):
        messages.error(request, 'Para recibir avisos debes asignar fecha y hora a la tarea.')
        return redirect('academico:home_estudiante')
    tarea.recordatorios_activos = decision == 'si'
    tarea.save(update_fields=['recordatorios_activos'])
    messages.success(request, 'Recordatorios internos activados.' if decision == 'si' else 'Recordatorios desactivados.')
    return redirect('academico:home_estudiante')


@login_required
@require_http_methods(['POST'])
def recordatorios_estudiante(request):
    from .models import RecordatorioTarea
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    RecordatorioTarea.objects.filter(estudiante=request.user, leido=False).update(leido=True)
    return redirect('academico:home_estudiante')
