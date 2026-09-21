from django.urls import path

from . import views

app_name = 'academico'

urlpatterns = [
    path('docente/', views.home_docente, name='home_docente'),
    path('apoderado/', views.home_apoderado, name='home_apoderado'),
    path('apoderado/estudiante/<int:estudiante_id>/', views.detalle_estudiante, name='detalle_estudiante'),
    path('apoderado/estudiante/<int:estudiante_id>/justificacion/nueva/', views.crear_justificacion, name='crear_justificacion'),
    path('administrativo/', views.home_administrativo, name='home_administrativo'),
    path('administrativo/cursos/nuevo/', views.crear_curso, name='crear_curso'),
    path('administrativo/eventos/nuevo/', views.crear_evento, name='crear_evento'),
    path('crear-observacion/', views.crear_observacion, name='crear_observacion'),
    path('ajax/cargar-estudiantes/', views.cargar_estudiantes, name='ajax_cargar_estudiantes'),
    path('observaciones/panel/', views.lista_observaciones, name='lista_observaciones'),
    path('observaciones/actualizar/<int:pk>/', views.actualizar_observacion, name='actualizar_observacion'),

]
