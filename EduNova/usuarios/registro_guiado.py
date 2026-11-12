"""Registro guiado por rol. Estudiantes verifican su correo antes de activar la cuenta."""
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from academico.models import Asignatura, Carrera, CarreraAsignatura, Curso, Estudiante, MencionCarrera, PlanAsignatura, PeriodoAcademico
from .forms import RegistroForm
from .models import Usuario
from .verificacion_registro import SESSION_KEY, ErrorCorreoEstudiante, crear_verificacion
from .verificacion_roles import (SESSION_KEY_ROLES, ErrorCorreoRol, crear_verificacion_rol)


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
    """Alta básica para los tres perfiles, sin consultar catálogos académicos."""
    if request.user.is_authenticated:
        return redirect('usuarios:post_login_redirect')
    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        rol = form.cleaned_data['rol']
        try:
            with transaction.atomic():
                usuario = form.save(commit=False)
                usuario.is_active = False
                usuario.save()
                if rol == Usuario.Rol.ESTUDIANTE:
                    crear_verificacion(request, usuario)
                else:
                    crear_verificacion_rol(request, usuario)
        except (ErrorCorreoEstudiante, ErrorCorreoRol) as exc:
            form.add_error(None, str(exc))
        else:
            clave = SESSION_KEY if rol == Usuario.Rol.ESTUDIANTE else SESSION_KEY_ROLES
            request.session[clave] = usuario.pk
            return redirect('usuarios:verificar_registro_estudiante' if rol == Usuario.Rol.ESTUDIANTE
                            else 'usuarios:verificar_registro_rol')
    return render(request, 'usuarios/registro.html', {'form': form})


def registro_estudiante_guiado(request):
    """URL histórica; ambas rutas comparten ahora el registro por roles."""
    return redirect('usuarios:registro')
