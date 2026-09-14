from django.urls import path

from . import views

app_name = 'comunicacion'

urlpatterns = [
    path('nuevo/', views.enviar_comunicado, name='enviar_comunicado'),
    path('', views.bandeja, name='bandeja'),
    path('<int:mensaje_id>/', views.detalle_mensaje, name='detalle_mensaje'),
    path('panel-notificaciones/', views.panel_notificaciones, name='panel_notificaciones'),
]
