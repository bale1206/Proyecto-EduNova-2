from django.urls import path

from . import views
from . import csv_views

app_name = 'academico'

urlpatterns = [
    path('administrativo/secciones/opciones/', views.opciones_seccion, name='opciones_seccion'),
    path('csv/', csv_views.panel_csv, name='panel_csv'),
    path('csv/<str:tipo>/exportar/', csv_views.exportar_csv, name='exportar_csv'),
    path('csv/<str:tipo>/plantilla/', csv_views.plantilla_csv, name='plantilla_csv'),
    path('csv/<str:tipo>/importar/', csv_views.importar_csv, name='importar_csv'),
    path('estudiante/', views.home_estudiante, name='home_estudiante'),
    path('estudiante/recordatorios/', views.recordatorios_estudiante, name='recordatorios_estudiante'),
    path('estudiante/tareas/<int:tarea_id>/recordatorio/', views.configurar_recordatorio, name='configurar_recordatorio'),
    path('estudiante/tareas/nueva/', views.crear_tarea_estudiante, name='crear_tarea_estudiante'),
    path('estudiante/tareas/<int:tarea_id>/alternar/', views.alternar_tarea_estudiante, name='alternar_tarea_estudiante'),
    path('estudiante/tareas/<int:tarea_id>/eliminar/', views.eliminar_tarea_estudiante, name='eliminar_tarea_estudiante'),
    path('docente/', views.home_docente, name='home_docente'),
    path('planificacion/tareas/nueva/', views.crear_tarea_equipo, name='crear_tarea_equipo'),
    path('planificacion/tareas/<int:tarea_id>/<str:accion>/', views.tarea_equipo_accion, name='tarea_equipo_accion'),
    path('planificacion/recordatorios/', views.recordatorios_equipo, name='recordatorios_equipo'),
    path('apoderado/', views.home_apoderado, name='home_apoderado'),
    path('apoderado/estudiante/<int:estudiante_id>/', views.detalle_estudiante, name='detalle_estudiante'),
    path('apoderado/estudiante/<int:estudiante_id>/justificacion/nueva/', views.crear_justificacion, name='crear_justificacion'),
    path('administrativo/', views.home_administrativo, name='home_administrativo'),
    path('administrativo/analitica/', views.analitica_carrera, name='analitica_carrera'),
    path('administrativo/carreras/nueva/', views.crear_carrera, name='crear_carrera'),
    path('administrativo/carreras/asignar/', views.asignar_carrera, name='asignar_carrera'),
    path('administrativo/secciones/matricular/', views.matricular_seccion, name='matricular_seccion'),
    path('administrativo/cursos/nuevo/', views.crear_curso, name='crear_curso'),
    path('administrativo/eventos/nuevo/', views.crear_evento, name='crear_evento'),
    path('crear-observacion/', views.crear_observacion, name='crear_observacion'),
    path('ajax/cargar-estudiantes/', views.cargar_estudiantes, name='ajax_cargar_estudiantes'),
    path('observaciones/panel/', views.lista_observaciones, name='lista_observaciones'),
    path('observaciones/actualizar/<int:pk>/', views.actualizar_observacion, name='actualizar_observacion'),
    path('asistencia/tomar/', views.tomar_asistencia, name='tomar_asistencia'),

]
