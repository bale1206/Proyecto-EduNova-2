from django.urls import path

from . import views
from .registro_guiado import registro_estudiante_guiado

app_name = 'usuarios'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('registro/estudiante/', registro_estudiante_guiado, name='registro_estudiante_guiado'),
    path('logout/', views.logout_view, name='logout'),
    path('redirigir/', views.post_login_redirect, name='post_login_redirect'),
]
