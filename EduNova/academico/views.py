import calendar as cal
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
                'es_hoy': dia == timezone.localdate().day and month == timezone.localdate().month and year == timezone.localdate().year,
            })
        semanas.append(fila)
    return semanas


def _mes_actual_o_parametro(request):
    hoy = timezone.localdate()
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
    """Analítica por asignatura y sección SOLO para las carreras del director."""
    if request.user.is_superuser:
        carreras = Carrera.objects.all().order_by('escuela', 'nombre')
    else:
        _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
        carreras = _carreras_director(request.user)

    carrera_id = request.GET.get('carrera', '')
    if carrera_id and not carrera_id.isdecimal():
        raise PermissionDenied('Selecciona una carrera autorizada.')
    if carrera_id:
        carrera = get_object_or_404(carreras, pk=carrera_id)
    else:
        carrera = carreras.filter(pk=request.user.carrera_dirigida_id).first() or carreras.first()

    asignaturas = (Asignatura.objects.filter(carreras=carrera).distinct().order_by('nombre', 'codigo')
                   if carrera else Asignatura.objects.none())
    codigo = request.GET.get('asignatura', '')
    elegida = asignaturas.filter(pk=codigo).first() if codigo.isdecimal() else None
    if not elegida:
        elegida = asignaturas.first()
    disponibles = (Curso.objects.filter(asignatura_catalogo=elegida).order_by('seccion')
                   if elegida else Curso.objects.none())
    seccion_id = request.GET.get('seccion', '')
    if not seccion_id.isdecimal() or not disponibles.filter(pk=seccion_id).exists():
        seccion_id = ''
    visibles = disponibles.filter(pk=seccion_id) if seccion_id else disponibles
    resumen = resumir_asistencia(visibles, carrera) if carrera else {}
    return render(request, 'academico/analitica_carrera.html', {
        'carreras': carreras, 'carrera': carrera, 'asignaturas': asignaturas,
        'asignatura_seleccionada': elegida,
        'secciones_disponibles': disponibles, 'seccion_seleccionada': seccion_id,
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
    """La creación de secciones corresponde al equipo técnico, no a directores."""
    if not request.user.is_superuser:
        raise PermissionDenied('Solo Django Admin puede crear secciones.')
    return redirect('admin:academico_curso_add')


@login_required
def opciones_seccion(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Solo Django Admin puede administrar secciones.')
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
    """Publicación compartida, restringida a secciones docentes o carreras dirigidas."""
    if request.user.rol not in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
        raise PermissionDenied('Solo docentes y directores pueden publicar actividades.')
    from datetime import time
    tipo = request.POST.get('tipo', '')
    permitidos = ({Evento.Tipo.REUNION, Evento.Tipo.EVALUACION, Evento.Tipo.OTRO}
                  if request.user.rol == Usuario.Rol.DOCENTE else
                  {Evento.Tipo.REUNION, Evento.Tipo.OTRO})
    if tipo not in permitidos:
        raise PermissionDenied('Tipo de actividad no permitido para este rol.')
    titulo = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    if not titulo or len(titulo) > 150:
        messages.error(request, 'Escribe un título válido, máximo 150 caracteres.')
        return redirect(_portal_url(request.user))
    try:
        fecha = date.fromisoformat(request.POST.get('fecha', ''))
        hora = time.fromisoformat(request.POST['hora_inicio']) if request.POST.get('hora_inicio') else None
        fin = time.fromisoformat(request.POST['hora_fin']) if request.POST.get('hora_fin') else None
    except (ValueError, TypeError):
        messages.error(request, 'Selecciona una fecha y horas válidas.')
        return redirect(_portal_url(request.user))
    if hora and fin and fin <= hora:
        messages.error(request, 'El término debe ser posterior al inicio.')
        return redirect(_portal_url(request.user))

    carrera = None
    seccion = None

    Evento.objects.create(curso=seccion, carrera=carrera, creado_por=request.user,
                          tipo=tipo, titulo=titulo, descripcion=descripcion,
                          fecha=fecha, hora_inicio=hora, hora_fin=fin)
    messages.success(request, 'Actividad guardada en tu calendario personal.')
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


def _carreras_director(user):
    """Un director solo accede a sus carreras, incluidas las vinculaciones históricas."""
    if user.rol != Usuario.Rol.ADMINISTRATIVO:
        return Carrera.objects.none()
    return Carrera.objects.filter(
        Q(directores_asignados=user) | Q(pk=user.carrera_dirigida_id)
    ).distinct().order_by('escuela', 'nombre')


def _secciones_planificador(user):
    if user.rol == Usuario.Rol.DOCENTE:
        return Curso.objects.filter(Q(docentes=user) | Q(docente_jefe=user)).distinct()
    # Dirección de carrera no publica ni gestiona actividades por sección.
    return Curso.objects.none()


def _portal_planificacion(request):
    return _portal_personal(request)


def _portal_personal(request):
    """Calendario privado sin filtros ni dependencias de los catálogos históricos."""
    from datetime import time
    from .horario_personal import clases_personales_por_dia
    from .programacion_tareas import fechas_tarea
    user = request.user
    es_estudiante = user.rol == Usuario.Rol.ESTUDIANTE
    es_director = user.rol == Usuario.Rol.ADMINISTRATIVO
    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    inicio, final = date(year, month, 1), date(year, month, cal.monthrange(year, month)[1])
    eventos = Evento.objects.filter(creado_por=user).order_by('fecha', 'hora_inicio')
    tareas = TareaEstudio.objects.filter(estudiante=user).order_by('completada', 'fecha_limite', 'hora_inicio')
    semanas = _construir_calendario(year, month, eventos.filter(fecha__range=(inicio, final)))
    clases = {} if es_director else clases_personales_por_dia(user, year, month)
    ocurrencias = {}
    for tarea in tareas:
        for fecha in fechas_tarea(tarea, inicio, final):
            ocurrencias.setdefault(fecha.day, []).append(tarea)
    for semana in semanas:
        for dia in semana:
            dia['clases'] = clases.get(dia['numero'], [])
            dia['tareas'] = ocurrencias.get(dia['numero'], [])
    hoy = timezone.localdate()
    proximos = eventos.filter(fecha__gte=hoy)
    agenda = [{'fecha': e.fecha, 'titulo': e.titulo, 'tipo': e.get_tipo_display(), 'hora': e.hora_inicio}
              for e in proximos[:20]]
    agenda += [{'fecha': t.fecha_limite, 'titulo': t.titulo, 'tipo': t.get_tipo_actividad_display(), 'hora': t.hora_inicio}
               for t in tareas if not t.completada and t.fecha_limite and t.fecha_limite >= hoy]
    agenda.sort(key=lambda x: (x['fecha'], x['hora'] or time.min))
    contexto = {
        'semanas': semanas, 'mes_nombre': MESES_ES[month], 'anio': year, 'mes': month,
        'prev_year': prev_y, 'prev_month': prev_m, 'next_year': next_y, 'next_month': next_m,
        'tareas': tareas, 'pendientes': tareas.filter(completada=False),
        'es_director': es_director, 'proximos_eventos': proximos[:8], 'agenda_proxima': agenda[:6],
        'bloques_horario': user.bloques_horario.all(),
        'recordatorios_no_leidos': user.recordatorios_tareas.filter(leido=False).count(),
        'recordatorios_recientes': user.recordatorios_tareas.filter(leido=False)[:8],
        'avisos_asistencia': AvisoAsistencia.objects.filter(destinatario=user)[:5],
        'tarea_para_configurar': (tareas.filter(pk=request.GET.get('configurar_tarea')).first()
            if request.GET.get('configurar_tarea', '').isdecimal() else None),
    }
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'academico/_calendario.html', contexto)
    return render(request, 'academico/home_estudiante.html' if es_estudiante else 'academico/planificacion_equipo.html', contexto)


@login_required
@require_http_methods(['POST'])
def crear_tarea_equipo(request):
    from datetime import time
    import re
    if request.user.rol != Usuario.Rol.DOCENTE:
        raise PermissionDenied('El director únicamente agenda reuniones y eventos.')
    titulo = request.POST.get('titulo', '').strip()
    if not titulo or len(titulo) > 160:
        messages.error(request, 'Título inválido.')
        return redirect(_portal_url(request.user))
    seccion = None
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
    if request.user.rol != Usuario.Rol.DOCENTE:
        raise PermissionDenied('La dirección no administra tareas privadas desde este portal.')
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
    if request.user.rol != Usuario.Rol.DOCENTE:
        raise PermissionDenied('La dirección solo gestiona reuniones y eventos.')
    request.user.recordatorios_tareas.filter(leido=False).update(leido=True)
    return redirect(_portal_url(request.user))


@login_required
def home_estudiante(request):
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    return _portal_personal(request)


@login_required
@require_http_methods(['GET', 'POST'])
def ajustar_secciones_estudiante(request):
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    return redirect('academico:importar_horario')


@login_required
def crear_tarea_estudiante(request):
    from datetime import datetime
    from .models import TareaEstudio
    from django.views.decorators.http import require_POST
    _requerir_rol(request, Usuario.Rol.ESTUDIANTE)
    if request.method != 'POST':
        raise PermissionDenied('Acción no permitida.')
    tipo_actividad = request.POST.get('tipo_actividad', 'tarea')
    if tipo_actividad not in TareaEstudio.TipoActividad.values:
        raise PermissionDenied('Tipo de actividad no permitido.')
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
            seccion = None
            color = request.POST.get('color', '#4C849D').upper()
            if not re.fullmatch(r'#[0-9A-F]{6}', color):
                color = '#4C849D'
            prioridad = request.POST.get('prioridad', 'media')
            if prioridad not in ('alta', 'media', 'baja'):
                prioridad = 'media'
            tarea = TareaEstudio.objects.create(
                estudiante=request.user, tipo_actividad=tipo_actividad,
                titulo=titulo, descripcion=request.POST.get('descripcion', '').strip()[:2000],
                fecha_limite=fecha, seccion=seccion, color=color,
                prioridad=prioridad, hora_inicio=hora, repeticion=repeticion,
                minutos_antes=minutos_antes,
            )
            if tipo_actividad == TareaEstudio.TipoActividad.TAREA:
                messages.success(request, 'Tarea creada. Decide si deseas recordatorios.')
                return redirect(f"{reverse('academico:home_estudiante')}?configurar_tarea={tarea.pk}#configurar-recordatorio")
            messages.success(request, f'{tarea.get_tipo_actividad_display()} agregada a tu calendario personal.')
            return redirect('academico:home_estudiante')
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
