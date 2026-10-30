from django.urls import path

from . import views
from .registro_guiado import registro_estudiante_guiado
from .verificacion_prueba import probar_codigo_correo
from .verificacion_registro import verificar_registro_estudiante

app_name = 'usuarios'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('registro/estudiante/', registro_estudiante_guiado, name='registro_estudiante_guiado'),
    path('verificacion/prueba/', probar_codigo_correo, name='verificacion_prueba'),
    path('registro/verificar-correo/', verificar_registro_estudiante, name='verificar_registro_estudiante'),
    path('logout/', views.logout_view, name='logout'),
    path('redirigir/', views.post_login_redirect, name='post_login_redirect'),
]
