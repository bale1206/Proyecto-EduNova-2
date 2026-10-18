from datetime import datetime, time
from django.db import migrations
from django.utils import timezone


def importar_historial(apps, schema_editor):
    db = schema_editor.connection.alias
    Sesion = apps.get_model('academico', 'SesionClase')
    Marca = apps.get_model('academico', 'MarcaAsistencia')
    Registro = apps.get_model('academico', 'RegistroAsistencia')
    Asistencia = apps.get_model('academico', 'Asistencia')
    # Los registros modernos existentes siempre tienen prioridad.
    originales = set(Marca.objects.using(db).values_list('sesion__seccion_id', 'sesion__fecha', 'estudiante_id'))
    ocupados = set()
    sesiones_creadas = set()
    ultimas_fechas = {}

    def seccion_estudiante(estudiante):
        if estudiante.curso_id:
            return estudiante.curso
        secciones = list(estudiante.secciones.using(db).all()[:2])
        return secciones[0] if len(secciones) == 1 else None

    def insertar(estudiante, seccion, docente_id, fecha, presente, instante):
        if seccion is None or docente_id is None:
            return
        clave = (seccion.pk, fecha, estudiante.pk)
        if clave in originales:
            return
        sesion, creada = Sesion.objects.using(db).get_or_create(seccion_id=seccion.pk, fecha=fecha, defaults={'docente_id': docente_id})
        if creada:
            sesiones_creadas.add(sesion.pk)
        if sesion.pk in sesiones_creadas:
            ultimas_fechas[sesion.pk] = max(ultimas_fechas.get(sesion.pk, instante), instante)
        marca, _ = Marca.objects.using(db).update_or_create(sesion_id=sesion.pk, estudiante_id=estudiante.pk, defaults={'presente': presente})
        Marca.objects.using(db).filter(pk=marca.pk).update(actualizado_en=instante)
        ocupados.add(clave)

    # Fecha/hora de RegistroAsistencia: prevalece la última corrección de cada día.
    for registro in Registro.objects.using(db).select_related('estudiante__curso', 'seccion').order_by('fecha', 'pk').iterator():
        seccion = registro.seccion or seccion_estudiante(registro.estudiante)
        if seccion:
            Registro.objects.using(db).filter(pk=registro.pk).update(seccion_id=seccion.pk)
            fecha = timezone.localtime(registro.fecha).date()
            insertar(registro.estudiante, seccion, registro.docente_id, fecha, registro.presente, registro.fecha)
    registros_importados = set(ocupados)
    # El modelo escolar conserva estados y justificativos; completa huecos del análisis.
    for antigua in Asistencia.objects.using(db).select_related('estudiante__curso').order_by('fecha', 'pk').iterator():
        seccion = seccion_estudiante(antigua.estudiante)
        if not seccion or (seccion.pk, antigua.fecha, antigua.estudiante_id) in registros_importados:
            continue
        docente_id = antigua.registrado_por_id or seccion.docente_jefe_id
        instante = timezone.make_aware(datetime.combine(antigua.fecha, time.min))
        insertar(antigua.estudiante, seccion, docente_id, antigua.fecha, antigua.estado in ('presente', 'atraso'), instante)
    for sesion_id, instante in ultimas_fechas.items():
        Sesion.objects.using(db).filter(pk=sesion_id).update(actualizada_en=instante)


class Migration(migrations.Migration):
    dependencies = [('academico', '0014_secciones_asistencia')]
    operations = [migrations.RunPython(importar_historial, migrations.RunPython.noop)]
