import calendar as cal
from datetime import date

from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from comunicacion.services import mensajes_no_leidos
from usuarios.models import Usuario

from .forms import ActividadAdministrativaForm, CrearSeccionForm, CarreraForm, AsignarCarreraForm, MatricularSeccionForm, CursoForm, EventoForm, JustificacionRetiroForm, ObservacionForm, ActualizarObservacionForm
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
def home_administrativo(request, evento_form=None):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    carrera = request.user.carrera_dirigida
    # La agenda permite usar todas las secciones, incluidas las históricas sin catálogo.
    cursos = Curso.objects.select_related('docente_jefe', 'asignatura_catalogo').order_by('asignatura', 'seccion')
    seleccion = request.GET.get('seccion', '')
    if not seleccion.isdecimal() or not cursos.filter(pk=seleccion).exists():
        seleccion = ''
    visibles = cursos.filter(pk=seleccion) if seleccion else cursos
    year, month = _mes_actual_o_parametro(request)
    (prev_y, prev_m), (next_y, next_m) = _mes_anterior_siguiente(year, month)
    eventos = Evento.objects.filter(curso__in=visibles, fecha__year=year, fecha__month=month)
    proximos = Evento.objects.filter(curso__in=cursos, fecha__gte=date.today()).select_related('curso').order_by('fecha','hora_inicio')[:8]
    form = evento_form if evento_form is not None else ActividadAdministrativaForm()
    contexto = {
        'carrera': carrera, 'cursos': cursos, 'seccion_seleccionada': seleccion,
        'curso_form': CrearSeccionForm(user=request.user, initial={'carrera': carrera.pk} if carrera else {}),
        'total_estudiantes': Estudiante.objects.count(),
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
def crear_evento(request):
    _requerir_rol(request, Usuario.Rol.ADMINISTRATIVO)
    if request.method == 'POST':
        form = ActividadAdministrativaForm(request.POST)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.creado_por = request.user
            evento.save()
            messages.success(request, f'"{evento.titulo}" agendado para {evento.curso}.')
            return redirect('academico:home_administrativo')
        messages.error(request, 'Revisa los datos del evento.')
        return home_administrativo(request, evento_form=form)
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
