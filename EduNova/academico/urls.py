from django.urls import path

from . import views

app_name = 'academico'

urlpatterns = [
    path('docente/', views.home_docente, name='home_docente'),
    path('apoderado/', views.home_apoderado, name='home_apoderado'),
    path('apoderado/estudiante/<int:estudiante_id>/', views.detalle_estudiante, name='detalle_estudiante'),
    path('administrativo/', views.home_administrativo, name='home_administrativo'),
    path('administrativo/cursos/nuevo/', views.crear_curso, name='crear_curso'),
    path('administrativo/eventos/nuevo/', views.crear_evento, name='crear_evento'),
]
