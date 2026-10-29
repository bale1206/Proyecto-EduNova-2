"""Servicio transaccional reutilizable: mallas versionadas y oferta académica.

Nunca crea cuentas ni inventa docentes. Importa incrementalmente (no borra
matrículas, secciones históricas ni asignaturas que falten del nuevo archivo).
"""
from collections import defaultdict
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from usuarios.models import Usuario
from .importacion_archivos import normalizar
from .models import (
    Asignatura, Carrera, CarreraAsignatura, Curso, HorarioSeccion,
    PeriodoAcademico, PlanEstudio, PlanAsignatura,
)
from .secciones import prefijo_asignatura


def aplicar_malla(preview, carrera, mencion, anio_ingreso):
    if preview['errores']:
        raise ValidationError('La malla contiene errores; corrígelos antes de importar.')
    if mencion and mencion.carrera_id != carrera.pk:
        raise ValidationError('La mención no pertenece a la carrera elegida.')
    if not 2000 <= int(anio_ingreso) <= 2100:
        raise ValidationError('Año de ingreso inválido.')
    with transaction.atomic():
        plan, _ = PlanEstudio.objects.get_or_create(
            carrera=carrera, mencion=mencion, anio_ingreso=anio_ingreso)
        nuevas, actualizadas = 0, 0
        for item in preview['filas']:
            asignatura, creada = Asignatura.objects.get_or_create(
                codigo=item['codigo'], defaults={'nombre': item['nombre'], 'activa': True})
            if creada:
                nuevas += 1
            # Los cambios de nombre en el código institucional existente requieren revisión manual.
            CarreraAsignatura.objects.get_or_create(
                carrera=carrera, mencion=mencion, asignatura=asignatura,
                defaults={'anio_plan': item['anio'], 'semestre_plan': item['semestre']})
            relacion, creada = PlanAsignatura.objects.update_or_create(
                plan=plan, asignatura=asignatura,
                defaults={'anio_curricular': item['anio'], 'semestre_curricular': item['semestre']})
            if not creada:
                actualizadas += 1
        # No se eliminan asignaturas del plan por ausencia en un archivo parcial.
    return {'plan': str(plan), 'filas': len(preview['filas']),
            'asignaturas_nuevas': nuevas, 'vinculos_actualizados': actualizadas,
            'politica': 'Incremental: no se retiran asignaturas ausentes.'}


def resolver_mapeo(preview, opciones, nuevas=None):
    """Resuelve carreras existentes o crea nuevas, solo al confirmar la importación.

    Se invoca dentro de transaction.atomic() en la vista. Verifica todas las
    propuestas antes de escribir y nunca permite crear carreras por accidente.
    Retorna (mapeo, cantidad_creadas).
    """
    nombres = list(preview['carreras'])
    catalogo = list(Carrera.objects.all())
    activas = {str(c.pk): c for c in catalogo if c.activa}
    catalogo_normalizado = {normalizar(c.nombre): c for c in catalogo}
    nuevas = nuevas or {}
    propuestas = []
    nombres_nuevos = set()
    mapeo = {}

    for origen in nombres:
        opcion = str(opciones.get(origen, '')).strip()
        if opcion == '__crear__':
            datos = nuevas.get(origen, {})
            nombre = ' '.join(str(datos.get('nombre', '')).split())
            escuela = ' '.join(str(datos.get('escuela', '')).split())
            if not nombre or len(nombre) > 180:
                raise ValidationError(
                    f'Indica un nombre válido (máximo 180 caracteres) para «{origen}».')
            if not escuela or len(escuela) > 120:
                raise ValidationError(
                    f'Indica una escuela válida (máximo 120 caracteres) para «{origen}».')
            nombre_normalizado = normalizar(nombre)
            if nombre_normalizado in catalogo_normalizado:
                carrera = catalogo_normalizado[nombre_normalizado]
                raise ValidationError(
                    f'«{nombre}» ya existe en EduNova (ID {carrera.pk}). '
                    'Asóciala a la carrera existente; si está inactiva, actívala desde Django Admin.')
            if nombre_normalizado in nombres_nuevos:
                raise ValidationError(
                    f'La carrera «{nombre}» se intentó crear más de una vez. '
                    'Usa nombres distintos o unifica la asociación antes de importar.')
            nombres_nuevos.add(nombre_normalizado)
            propuestas.append((origen, nombre, escuela))
        elif opcion:
            if opcion not in activas:
                raise ValidationError(
                    f'La carrera asociada a «{origen}» no existe o está inactiva.')
            mapeo[origen] = activas[opcion]

    if not mapeo and not propuestas:
        raise ValidationError(
            'Debes asociar o crear al menos una carrera del archivo.')

    # No se crean registros hasta que TODAS las filas seleccionadas pasen la validación.
    for origen, nombre, escuela in propuestas:
        carrera = Carrera.objects.create(nombre=nombre, escuela=escuela, activa=True)
        mapeo[origen] = carrera
    return mapeo, len(propuestas)


def _docentes_por_nombre():
    """El nombre completo no es una clave segura: coincidencias múltiples se omiten."""
    opciones = defaultdict(set)
    for doc in Usuario.objects.filter(rol=Usuario.Rol.DOCENTE, is_active=True):
        nombre = ' '.join(x for x in (doc.first_name, getattr(doc,'apellidos','')) if x).strip()
        if nombre:
            opciones[normalizar(nombre)].add(doc.pk)
    return opciones


def aplicar_oferta(preview, anio, semestre, mapeo):
    if preview['errores']:
        raise ValidationError('La oferta contiene filas contradictorias. Debes corregirla antes de importar.')
    if int(semestre) not in (1,2) or not 2000 <= int(anio) <= 2100:
        raise ValidationError('El año o semestre no es válido.')
    if not mapeo:
        raise ValidationError('No seleccionaste carreras que quieras importar.')

    grupos = [g for g in preview['grupos'].values() if any(c in mapeo for c in g['carreras'])]
    if not grupos:
        raise ValidationError('No hay secciones para las carreras asociadas.')
    if len(grupos) > 5000:
        raise ValidationError('Demasiadas secciones en una importación. Divide el archivo por carreras.')
    with transaction.atomic():
        periodo, _ = PeriodoAcademico.objects.get_or_create(
            anio=anio, semestre=semestre, sede='Antonio Varas')

        # Catálogo completo de códigos que intervienen en esta importación.
        codigos = {g['codigo'] for g in grupos}
        existentes = Asignatura.objects.filter(codigo__in=codigos)
        asignaturas = {a.codigo: a for a in existentes}
        primer_grupo = {g['codigo']: g for g in grupos}
        faltantes = [Asignatura(codigo=codigo, nombre=primer_grupo[codigo]['nombre'], activa=True)
                     for codigo in sorted(codigos) if codigo not in asignaturas]
        if faltantes:
            Asignatura.objects.bulk_create(faltantes, batch_size=250, ignore_conflicts=True)
            asignaturas = {a.codigo: a for a in Asignatura.objects.filter(codigo__in=codigos)}

        # Solo se crean vínculos de carrera provisionales si no existe uno en ninguna mención.
        asociados = set(CarreraAsignatura.objects.filter(
            carrera__in=list(mapeo.values()), asignatura__in=asignaturas.values()
        ).values_list('carrera_id','asignatura_id'))
        enlaces = []
        for g in grupos:
            for carrera_origen in g['carreras']:
                carrera = mapeo.get(carrera_origen)
                if not carrera:
                    continue
                pair = (carrera.pk, asignaturas[g['codigo']].pk)
                if pair not in asociados:
                    enlaces.append(CarreraAsignatura(carrera_id=pair[0], asignatura_id=pair[1]))
                    asociados.add(pair)
        if enlaces:
            CarreraAsignatura.objects.bulk_create(enlaces, batch_size=300, ignore_conflicts=True)

        # Secciones de otros períodos nunca se reutilizan ni modifican.
        existentes = {(c.asignatura_catalogo_id, c.codigo_institucional): c
                      for c in Curso.objects.filter(periodo_academico=periodo)}
        codigos_internos = Curso.objects.values_list('seccion', flat=True)
        max_prefijo = defaultdict(lambda: -1)
        for codigo in codigos_internos:
            parts = codigo.split('-')
            if len(parts)==3 and len(parts[0])==3 and parts[1].isdigit():
                max_prefijo[parts[0]] = max(max_prefijo[parts[0]], int(parts[1]))
        nuevos = []
        for g in grupos:
            clave = (asignaturas[g['codigo']].pk, g['seccion'])
            if clave in existentes:
                continue
            asignatura = asignaturas[g['codigo']]
            pref = prefijo_asignatura(asignatura.nombre)
            max_prefijo[pref] += 1
            if max_prefijo[pref] > 999:
                raise ValidationError(f'Se agotaron los correlativos internos para {pref}.')
            nuevos.append(Curso(
                periodo_academico=periodo, codigo_institucional=g['seccion'],
                asignatura_catalogo=asignatura, asignatura=asignatura.nombre,
                turno=(g['turno']=='D'), seccion=f'{pref}-{max_prefijo[pref]:03d}-'+g['turno'],
                docentes_oferta=', '.join(sorted(g['docentes'])),
            ))
        if nuevos:
            # Códigos internos ya calculados; bulk_create omite el generador de Curso.save.
            Curso.objects.bulk_create(nuevos, batch_size=200)
        secciones = {(c.asignatura_catalogo_id, c.codigo_institucional): c
                     for c in Curso.objects.filter(periodo_academico=periodo)}
        # Refresca nombres del mismo período sin inventar usuarios autenticados.
        actualizados = []
        for grupo in grupos:
            seccion = secciones[(asignaturas[grupo['codigo']].pk, grupo['seccion'])]
            nombres = ', '.join(sorted(grupo['docentes']))
            if seccion.docentes_oferta != nombres:
                seccion.docentes_oferta = nombres
                actualizados.append(seccion)
        if actualizados:
            Curso.objects.bulk_update(actualizados, ['docentes_oferta'], batch_size=250)

        # Solo reemplazar horarios de los grupos importados (nunca otro semestre).
        procesadas = [secciones[(asignaturas[g['codigo']].pk, g['seccion'])] for g in grupos]
        ids_con_horarios = [s.pk for s, g in zip(procesadas, grupos) if g['horarios']]
        if ids_con_horarios:
            HorarioSeccion.objects.filter(seccion_id__in=ids_con_horarios).delete()
        horarios = [HorarioSeccion(seccion=secciones[(asignaturas[g['codigo']].pk, g['seccion'])],
                                   dia_semana=d, hora_inicio=i, hora_fin=f)
                    for g in grupos for d,i,f in sorted(g['horarios'])]
        if horarios:
            HorarioSeccion.objects.bulk_create(horarios, batch_size=400, ignore_conflicts=True)

        # Solamente asociar docentes existentes y con coincidencia inequívoca.
        lookup = _docentes_por_nombre()
        through = Curso.docentes.through
        ids_secciones = [seccion.pk for seccion in procesadas]
        existentes_docentes = set(through.objects.filter(curso_id__in=ids_secciones)
                                  .values_list('curso_id', 'usuario_id'))
        links = []
        sin_resolver = set()
        for g in grupos:
            seccion = secciones[(asignaturas[g['codigo']].pk, g['seccion'])]
            for nombre in g['docentes']:
                candidatos = lookup.get(normalizar(nombre), set())
                if len(candidatos) == 1:
                    docente_id = next(iter(candidatos))
                    par = (seccion.pk, docente_id)
                    if par not in existentes_docentes:
                        links.append(through(curso_id=seccion.pk, usuario_id=docente_id))
                        existentes_docentes.add(par)
                else:
                    sin_resolver.add(nombre)
        if links:
            through.objects.bulk_create(links, batch_size=500, ignore_conflicts=True)
    return {
        'periodo': str(periodo), 'filas_origen': preview['total'],
        'secciones_procesadas': len(grupos), 'secciones_nuevas': len(nuevos),
        'horarios': len(horarios), 'docentes_vinculados': len(links),
        'docentes_por_asignar': sorted(sin_resolver)[:40],
        'carreras_omitidas': sorted(set(preview['carreras'])-set(mapeo)),
        'politica': 'Incremental: no borra secciones no presentes ni cambia otros semestres.',
    }
