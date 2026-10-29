"""Registro guiado por rol, reutiliza el modelo universitario real.

No implementa verificación de correo institucional ni cambios al inicio de sesión.
"""
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from academico.models import Asignatura, Carrera, CarreraAsignatura, Curso, Estudiante, MencionCarrera, PlanAsignatura, PeriodoAcademico
from .forms import RegistroForm
from .models import Usuario


def periodo_actual(hoy=None):
    hoy = hoy or timezone.localdate()
    semestre = 1 if 3 <= hoy.month <= 7 else 2 if 8 <= hoy.month <= 12 else None
    return hoy.year, semestre


def catalogos_carreras(carreras):
    """Carga carreras, asignaturas, docentes y horarios en pocos accesos a BD.

    Reutiliza secciones compartidas entre carreras sin volver a consultarlas.
    Nunca fabrica docentes u horarios que no estén en PostgreSQL.
    """
    planes = list(CarreraAsignatura.objects.filter(
        carrera__in=carreras, asignatura__activa=True,
    ).select_related('asignatura').order_by('asignatura__nombre'))
    versiones = list(PlanAsignatura.objects.filter(
        plan__carrera__in=carreras, asignatura__activa=True,
    ).select_related('plan', 'asignatura'))
    ids = {plan.asignatura_id for plan in planes} | {v.asignatura_id for v in versiones}
    secciones = Curso.objects.filter(asignatura_catalogo_id__in=ids)
    periodo_anio, periodo_sem = periodo_actual()
    actual = PeriodoAcademico.objects.filter(anio=periodo_anio, semestre=periodo_sem, sede='Antonio Varas').first() if periodo_sem else None
    if actual and Curso.objects.filter(periodo_academico=actual).exists():
        secciones = secciones.filter(periodo_academico=actual)
    secciones = secciones.select_related(
        'docente_jefe').prefetch_related('docentes', 'horarios').order_by('seccion')
    secciones_por_asignatura = {}
    for sec in secciones:
        docentes = list(sec.docentes.all())
        if sec.docente_jefe and sec.docente_jefe not in docentes:
            docentes.append(sec.docente_jefe)
        secciones_por_asignatura.setdefault(sec.asignatura_catalogo_id, []).append({
            'id': sec.pk, 'codigo': sec.codigo_institucional or sec.seccion,
            'modalidad': 'diurno' if sec.turno else 'vespertino',
            'docentes': [d.nombre_completo for d in docentes] or ([sec.docentes_oferta] if sec.docentes_oferta else ['Por confirmar']),
            'horarios': [str(h) for h in sec.horarios.all()] or ['Horario por confirmar'],
        })
    catalogos = {str(c.pk): [] for c in carreras}
    for plan in planes:
        catalogos[str(plan.carrera_id)].append({
            'id': plan.asignatura_id, 'nombre': plan.asignatura.nombre,
            'codigo': plan.asignatura.codigo, 'mencion': plan.mencion_id, 'anio': plan.anio_plan,
            'semestre': plan.semestre_plan,
            'cohorte': None,
            'secciones': secciones_por_asignatura.get(plan.asignatura_id, []),
        })
    for version in versiones:
        catalogos[str(version.plan.carrera_id)].append({
            'id': version.asignatura_id, 'nombre': version.asignatura.nombre,
            'codigo': version.asignatura.codigo, 'mencion': version.plan.mencion_id,
            'anio': version.anio_curricular, 'semestre': version.semestre_curricular,
            'cohorte': version.plan.anio_ingreso,
            'secciones': secciones_por_asignatura.get(version.asignatura_id, []),
        })
    return catalogos


def _secciones_activas_registro(queryset):
    anio, semestre = periodo_actual()
    periodo = PeriodoAcademico.objects.filter(anio=anio, semestre=semestre, sede='Antonio Varas').first() if semestre else None
    if periodo and Curso.objects.filter(periodo_academico=periodo).exists():
        return queryset.filter(periodo_academico=periodo)
    return queryset


def _ids_unicos(post, campo, errores):
    valores = post.getlist(campo)
    if not valores or any(not v.isdecimal() for v in valores) or len(set(valores)) != len(valores):
        errores.append(f'Selecciona opciones válidas sin repetir en {campo}.')
        return []
    return [int(v) for v in valores]


@require_http_methods(['GET', 'POST'])
def registro_guiado(request):
    if request.user.is_authenticated:
        return redirect('usuarios:post_login_redirect')

    anio_actual, semestre_actual = periodo_actual()
    carreras = list(Carrera.objects.filter(activa=True).order_by('escuela', 'nombre'))
    form = RegistroForm(request.POST or None)
    errores = []
    rol = request.POST.get('rol') if request.method == 'POST' else None
    carrera = None
    ingreso = None
    carreras_elegidas = []
    secciones = []
    asignaturas = []
    modalidad = ''
    menciones_elegidas = []
    menciones = list(MencionCarrera.objects.filter(
        activa=True, carrera__in=carreras,
    ).select_related('carrera').order_by('carrera__nombre', 'nombre'))

    if request.method == 'POST':
        if rol not in {Usuario.Rol.ESTUDIANTE, Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO}:
            errores.append('Selecciona el tipo de cuenta antes de continuar.')
        carreras_ids = []
        if rol == Usuario.Rol.ESTUDIANTE:
            carrera_raw = request.POST.get('carrera_id', '')
            carrera = next((c for c in carreras if str(c.pk) == carrera_raw), None)
            ingreso_raw = request.POST.get('anio_ingreso', '')
            ingreso = int(ingreso_raw) if ingreso_raw.isdecimal() else None
            if carrera is None:
                errores.append('Selecciona una carrera válida.')
            modalidad = request.POST.get('modalidad', '')
            if modalidad not in Estudiante.Modalidad.values:
                errores.append('Selecciona una modalidad válida: Diurno o Vespertino.')
            if request.POST.get('mencion_id'):
                errores.append('La mención ya no se selecciona durante el registro estudiantil.')
            if ingreso is None or not anio_actual - 3 <= ingreso <= anio_actual:
                errores.append('Selecciona un año de ingreso correspondiente a 1.º–4.º año.')
            seccion_ids = _ids_unicos(request.POST, 'secciones', errores)
            if carrera:
                # Sin selección de mención: toda la malla de la carrera, filtrada por modalidad.
                planes_permitidos = CarreraAsignatura.objects.filter(
                    carrera=carrera).values('asignatura_id')
                turno = modalidad == Estudiante.Modalidad.DIURNO
                secciones = list(_secciones_activas_registro(Curso.objects.filter(
                    pk__in=seccion_ids, asignatura_catalogo_id__in=planes_permitidos,
                    asignatura_catalogo__activa=True, turno=turno,
                )).select_related('asignatura_catalogo').distinct())
            if len(secciones) != len(seccion_ids):
                errores.append('Las secciones deben corresponder a tu carrera y modalidad seleccionadas.')
            if len({s.asignatura_catalogo_id for s in secciones}) != len(secciones):
                errores.append('Selecciona una sola sección por asignatura.')

        elif rol in (Usuario.Rol.DOCENTE, Usuario.Rol.ADMINISTRATIVO):
            carreras_ids = _ids_unicos(request.POST, 'carreras', errores)
            carreras_elegidas = [c for c in carreras if c.pk in carreras_ids]
            if len(carreras_elegidas) != len(carreras_ids):
                errores.append('Una de las carreras ya no está disponible.')
            if rol == Usuario.Rol.ADMINISTRATIVO:
                escuela = request.POST.get('escuela', '')
                if not escuela or any(c.escuela != escuela for c in carreras_elegidas):
                    errores.append('Las carreras del director deben pertenecer a la escuela elegida.')
            else:
                mencion_ids_raw = request.POST.getlist('menciones_docente')
                if (any(not x.isdecimal() for x in mencion_ids_raw)
                        or len(set(mencion_ids_raw)) != len(mencion_ids_raw)):
                    errores.append('Selecciona menciones válidas, sin repetir.')
                menciones_elegidas = [m for m in menciones if str(m.pk) in mencion_ids_raw
                                     and m.carrera in carreras_elegidas]
                if len(menciones_elegidas) != len(mencion_ids_raw):
                    errores.append('Las menciones deben pertenecer a las carreras seleccionadas.')
                for elegida in carreras_elegidas:
                    if any(m.carrera_id == elegida.pk for m in menciones) and not any(
                            m.carrera_id == elegida.pk for m in menciones_elegidas):
                        errores.append(f'Selecciona una mención de {elegida.nombre}.')
                asignatura_ids = _ids_unicos(request.POST, 'asignaturas', errores)
                seccion_ids = _ids_unicos(request.POST, 'secciones', errores)
                planes_permitidos = CarreraAsignatura.objects.filter(
                    carrera__in=carreras_elegidas,
                ).filter(Q(mencion__isnull=True) | Q(mencion__in=menciones_elegidas)).values('asignatura_id')
                asignaturas = list(Asignatura.objects.filter(
                    pk__in=asignatura_ids, activa=True,
                    id__in=planes_permitidos).distinct())
                secciones = list(_secciones_activas_registro(Curso.objects.filter(
                    pk__in=seccion_ids, asignatura_catalogo__in=asignaturas,
                    asignatura_catalogo__carreras__in=carreras_elegidas))
                    .select_related('asignatura_catalogo').distinct())
                if len(asignaturas) != len(asignatura_ids):
                    errores.append('Las asignaturas deben pertenecer a las carreras seleccionadas.')
                if len(secciones) != len(seccion_ids):
                    errores.append('Las secciones deben pertenecer a las asignaturas seleccionadas.')
                if len({sec.asignatura_catalogo_id for sec in secciones}) != len(asignaturas):
                    errores.append('Selecciona al menos una sección de cada asignatura elegida.')

        if form.is_valid() and not errores:
            with transaction.atomic():
                usuario = form.save(commit=False)
                usuario.rol = rol
                if rol == Usuario.Rol.ADMINISTRATIVO:
                    # Campo histórico para compatibilidad con el portal de dirección.
                    usuario.carrera_dirigida = carreras_elegidas[0]
                usuario.save()
                if rol == Usuario.Rol.ESTUDIANTE:
                    perfil = Estudiante.objects.select_for_update().get(usuario=usuario)
                    perfil.carrera = carrera
                    perfil.modalidad = modalidad
                    perfil.mencion = None  # Ya no se solicita mención al estudiante.
                    perfil.anio_ingreso = ingreso
                    perfil.anio_carrera = anio_actual - ingreso + 1
                    perfil.curso = secciones[0]  # Compatibilidad; matrícula real es M2M.
                    perfil.save(update_fields=['carrera', 'modalidad', 'mencion', 'anio_ingreso', 'anio_carrera', 'curso'])
                    perfil.secciones.set(secciones)
                elif rol == Usuario.Rol.DOCENTE:
                    usuario.carreras_docencia.set(carreras_elegidas)
                    usuario.menciones_docencia.set(menciones_elegidas)
                    usuario.asignaturas_asociadas.set(asignaturas)
                    for seccion in secciones:
                        seccion.docentes.add(usuario)
                else:
                    usuario.carreras_dirigidas.set(carreras_elegidas)
            # No cambiar el login automático: ese cambio quedó pendiente por solicitud.
            login(request, usuario)
            messages.success(request, 'Cuenta creada y selección académica guardada.')
            return redirect('usuarios:post_login_redirect')
        for err in errores:
            form.add_error(None, err)

    return render(request, 'usuarios/registro.html', {
        'form': form, 'carreras': carreras,
        'menciones_json': [
            {'id': m.pk, 'carrera_id': m.carrera_id, 'nombre': m.nombre}
            for m in menciones
        ],
        'anio_actual': anio_actual, 'semestre_actual': semestre_actual,
        'anios_ingreso': range(anio_actual - 3, anio_actual + 1),
        'catalogos': catalogos_carreras(carreras),
        'carreras_json': [{'id': c.pk, 'nombre': c.nombre, 'escuela': c.escuela} for c in carreras],
        'registro_fallido': request.method == 'POST',
        'preseleccion': {
            'rol': request.POST.get('rol', ''),
            'carreras': request.POST.getlist('carreras'),
            'menciones_docente': request.POST.getlist('menciones_docente'),
            'asignaturas': request.POST.getlist('asignaturas'),
            'secciones': request.POST.getlist('secciones'),
        } if request.method == 'POST' else {},
    })


def registro_estudiante_guiado(request):
    """URL histórica; ambas rutas comparten ahora el registro por roles."""
    return redirect('usuarios:registro')
