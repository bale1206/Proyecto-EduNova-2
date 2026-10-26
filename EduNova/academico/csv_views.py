"""Dos planillas CSV orientadas a roles y datos académicos, nunca a tablas SQL genéricas."""
import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from usuarios.models import Usuario
from .models import Carrera, Estudiante, Asignatura

MAX_BYTES = 5 * 1024 * 1024
MAX_FILAS = 10000
FORMATOS = {
    'docentes': ['rut', 'codigos_asignaturas'],
    'estudiantes': ['rut', 'carrera', 'anio_carrera', 'estado_avance'],
}


def _verificar(request, tipo):
    if request.user.rol != Usuario.Rol.ADMINISTRATIVO:
        raise PermissionDenied('Solo la dirección de carrera puede gestionar planillas.')
    if tipo not in FORMATOS:
        raise PermissionDenied('La planilla solicitada no existe.')
    if not request.user.carrera_dirigida_id:
        raise PermissionDenied('Se requiere una carrera asignada al director.')


def _normalizar_rut(valor):
    return valor.strip().upper().replace('.', '')


def _respuesta(tipo, plantilla=False):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="edunova_{tipo}{"_plantilla" if plantilla else ""}.csv"'
    response['Cache-Control'] = 'no-store'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(FORMATOS[tipo])
    return response, writer


@login_required
@require_GET
def panel_csv(request):
    _verificar(request, 'estudiantes')
    return render(request, 'academico/panel_csv.html', {'carrera': request.user.carrera_dirigida})


@login_required
@require_GET
def plantilla_csv(request, tipo):
    _verificar(request, tipo)
    response, _ = _respuesta(tipo, plantilla=True)
    return response


@login_required
@require_GET
def exportar_csv(request, tipo):
    _verificar(request, tipo)
    response, writer = _respuesta(tipo)
    carrera = request.user.carrera_dirigida
    if tipo == 'estudiantes':
        qs = Estudiante.objects.filter(carrera=carrera).select_related('carrera').order_by('rut_estudiante')
        for alumno in qs.iterator():
            writer.writerow([alumno.rut_estudiante, alumno.carrera.nombre,
                             alumno.anio_carrera or '', alumno.estado_avance])
    else:
        # La planilla docente no muestra la carrera, solo códigos académicos.
        codigos = set(Asignatura.objects.filter(carreras=carrera).values_list('pk', flat=True))
        docentes = Usuario.objects.filter(rol=Usuario.Rol.DOCENTE).filter(
            asignaturas_asociadas__pk__in=codigos
        ).distinct().prefetch_related('asignaturas_asociadas').order_by('rut')
        for docente in docentes:
            writer.writerow([docente.rut, ';'.join(sorted(a.codigo for a in docente.asignaturas_asociadas.all() if a.pk in codigos))])
    return response


def _leer_archivo(archivo, tipo):
    if not archivo or not archivo.name.lower().endswith('.csv'):
        raise ValueError('Debes seleccionar un archivo CSV válido.')
    if archivo.size > MAX_BYTES:
        raise ValueError('El máximo permitido es 5 MB.')
    try:
        data = archivo.read(MAX_BYTES + 1).decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('La planilla debe usar codificación UTF-8.') from exc
    if '\x00' in data or len(data.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Archivo demasiado grande o con caracteres no permitidos.')
    rows = list(csv.reader(io.StringIO(data, newline=''), strict=True))
    if not rows or rows[0] != FORMATOS[tipo]:
        raise ValueError('Columnas incorrectas: ' + ', '.join(FORMATOS[tipo]))
    if len(rows) - 1 > MAX_FILAS:
        raise ValueError('Máximo 10.000 registros.')
    seen = set()
    for line, row in enumerate(rows[1:], 2):
        if len(row) != len(FORMATOS[tipo]):
            raise ValueError(f'Fila {line}: cantidad de columnas incorrecta.')
        rut = _normalizar_rut(row[0])
        if not rut or rut in seen:
            raise ValueError(f'Fila {line}: RUT vacío o repetido.')
        row[0] = rut
        seen.add(rut)
    return rows[1:]


@login_required
@require_POST
def importar_csv(request, tipo):
    _verificar(request, tipo)
    carrera = request.user.carrera_dirigida
    try:
        filas = _leer_archivo(request.FILES.get('archivo'), tipo)
        if not filas:
            raise ValueError('La planilla está vacía.')
        actualizaciones = []
        for line, row in enumerate(filas, 2):
            rut = row[0]
            if tipo == 'estudiantes':
                estudiante = Estudiante.objects.filter(rut_estudiante=rut, carrera=carrera).first()
                if estudiante is None:
                    raise ValueError(f'Fila {line}: no existe un estudiante de tu carrera con RUT {rut}.')
                if row[1].strip().casefold() != carrera.nombre.casefold():
                    raise ValueError(f'Fila {line}: la carrera debe ser exactamente «{carrera.nombre}».')
                if row[2].strip() not in ('1', '2', '3', '4'):
                    raise ValueError(f'Fila {line}: año de carrera debe estar entre 1 y 4.')
                if row[3].strip() not in ('al_dia', 'con_retraso'):
                    raise ValueError(f'Fila {line}: estado_avance debe ser al_dia o con_retraso.')
                actualizaciones.append((estudiante, int(row[2]), row[3].strip()))
            else:
                docente = Usuario.objects.filter(rut=rut, rol=Usuario.Rol.DOCENTE).first()
                if docente is None:
                    raise ValueError(f'Fila {line}: no existe una cuenta docente con RUT {rut}.')
                codigos = [v.strip().upper() for v in row[1].split(';') if v.strip()]
                if not codigos or len(codigos) != len(set(codigos)):
                    raise ValueError(f'Fila {line}: indica uno o más códigos únicos separados por punto y coma.')
                asignaturas = list(Asignatura.objects.filter(codigo__in=codigos, carreras=carrera, activa=True).distinct())
                if len(asignaturas) != len(codigos):
                    raise ValueError(f'Fila {line}: uno o más códigos no existen en el catálogo de tu carrera.')
                actualizaciones.append((docente, asignaturas))
        # Ningún dato cambia mientras haya errores en otras filas.
        with transaction.atomic():
            if tipo == 'estudiantes':
                for estudiante, year, estado in actualizaciones:
                    estudiante.anio_carrera = year
                    estudiante.estado_avance = estado
                    estudiante.save(update_fields=['anio_carrera', 'estado_avance'])
            else:
                for docente, asignaturas in actualizaciones:
                    # No eliminar asignaturas de otras carreras gestionadas por otros directores.
                    propias = set(Asignatura.objects.filter(carreras=carrera).values_list('pk', flat=True))
                    actuales = set(docente.asignaturas_asociadas.values_list('pk', flat=True))
                    docente.asignaturas_asociadas.set((actuales - propias) | {a.pk for a in asignaturas})
        messages.success(request, f'Planilla de {tipo}: {len(actualizaciones)} registros actualizados.')
    except (ValueError, csv.Error) as exc:
        messages.error(request, f'No se aplicó ningún cambio: {exc}')
    return redirect('academico:panel_csv')
