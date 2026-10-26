"""Programar cada minuto para avisos internos cerca de la hora elegida."""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from academico.models import TareaEstudio, RecordatorioTarea
from academico.programacion_tareas import fechas_tarea, instante_aviso


class Command(BaseCommand):
    help = 'Genera recordatorios internos de tareas. Programar cada minuto.'

    def handle(self, *args, **options):
        ahora = timezone.now()
        hoy = timezone.localdate()
        # Incluir mañana: un aviso de 60 min puede corresponder a una tarea a las 00:15.
        desde, hasta = hoy - timedelta(days=1), hoy + timedelta(days=1)
        creados = 0
        tareas = TareaEstudio.objects.filter(recordatorios_activos=True, completada=False, fecha_limite__isnull=False, hora_inicio__isnull=False).select_related('estudiante','seccion')
        for tarea in tareas.iterator():
            for dia in fechas_tarea(tarea, desde, hasta):
                momento = instante_aviso(tarea, dia)
                # Permite pequeñas demoras del planificador; evita avisos históricos.
                if momento is None or not (momento <= ahora < momento + timedelta(minutes=5)):
                    continue
                texto = f'Recordatorio: {tarea.titulo} comienza el {dia:%d/%m/%Y} a las {tarea.hora_inicio:%H:%M}.'
                _, creado = RecordatorioTarea.objects.get_or_create(tarea=tarea, programado_para=momento,
                    defaults={'estudiante':tarea.estudiante, 'texto':texto})
                creados += int(creado)
        self.stdout.write(self.style.SUCCESS(f'Recordatorios internos nuevos: {creados}'))
