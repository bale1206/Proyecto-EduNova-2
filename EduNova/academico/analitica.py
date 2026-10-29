"""Resumen de asistencia sin contar dos veces las copias del mismo registro."""
from django.db.models import Q
from django.utils import timezone

from .models import Estudiante, MarcaAsistencia, RegistroAsistencia


def resumir_asistencia(secciones, carrera):
    secciones = list(secciones)
    ids = {seccion.pk for seccion in secciones}
    if not ids:
        return {'total_registros': 0, 'presentes': 0, 'ausentes': 0,
                'porcentaje': None, 'sin_carrera': 0, 'detalle': []}

    # El registro público permite inscribirse en una sección sin elegir carrera.
    # Conservar esas marcas y avisar en pantalla; una carrera conocida distinta
    # sigue excluida para respetar el filtro de carrera en materias compartidas.
    alumnos = Estudiante.objects.filter(
        Q(carrera=carrera) | Q(carrera__isnull=True)
    ) if carrera is not None else Estudiante.objects.all()
    historicos = alumnos.filter(Q(curso_id__in=ids) | Q(secciones__pk__in=ids)).distinct()
    seccion_unica = {}
    for alumno in historicos.prefetch_related('secciones'):
        inscritas = {seccion.pk for seccion in alumno.secciones.all()}
        if alumno.curso_id:
            inscritas.add(alumno.curso_id)
        # Los modelos sin sección no permiten atribuir una marca a varias materias.
        if len(inscritas) == 1:
            seccion_unica[alumno.pk] = inscritas.pop()

    registros = {}
    eliminadas = set(MarcaAsistencia.objects.filter(
        estudiante__in=alumnos, sesion__seccion__isnull=True,
    ).values_list('estudiante_id', 'sesion__fecha'))
    # Prioridad: lista por sesión > registro histórico de asistencia.
    historiales = RegistroAsistencia.objects.filter(estudiante__in=alumnos).filter(
        Q(seccion_id__in=ids) | Q(seccion__isnull=True, estudiante_id__in=seccion_unica)
    ).select_related('estudiante').order_by('fecha', 'pk')
    for registro in historiales.iterator():
        seccion_id = registro.seccion_id or seccion_unica[registro.estudiante_id]
        # Un historial de una sección eliminada nunca se reasigna a la actual.
        if registro.seccion_id is None and (registro.estudiante_id, timezone.localtime(registro.fecha).date()) in eliminadas:
            continue
        clave = (seccion_id, timezone.localtime(registro.fecha).date(), registro.estudiante_id)
        registros[clave] = (registro.presente, registro.estudiante.carrera_id is None)

    marcas = MarcaAsistencia.objects.filter(
        sesion__seccion_id__in=ids, estudiante__in=alumnos,
    ).values_list('sesion__seccion_id', 'sesion__fecha', 'estudiante_id', 'presente', 'estudiante__carrera_id')
    for seccion_id, fecha, alumno_id, presente, carrera_id in marcas.iterator():
        registros[(seccion_id, fecha, alumno_id)] = (presente, carrera_id is None)

    conteos = {pk: [0, 0] for pk in ids}
    for (seccion_id, fecha, alumno_id), (presente, sin_carrera) in registros.items():
        conteos[seccion_id][0] += 1
        conteos[seccion_id][1] += int(presente)
    total = len(registros)
    presentes = sum(int(presente) for presente, _ in registros.values())
    detalle = []
    for seccion in secciones:
        cantidad, asistencias = conteos[seccion.pk]
        detalle.append({'seccion': seccion, 'total': cantidad, 'presentes': asistencias,
                        'porcentaje': round(asistencias * 100 / cantidad, 1) if cantidad else None})
    return {'total_registros': total, 'presentes': presentes, 'ausentes': total - presentes,
            'porcentaje': round(presentes * 100 / total, 1) if total else None,
            'sin_carrera': sum(int(sin_carrera) for _, sin_carrera in registros.values()),
            'detalle': detalle}
