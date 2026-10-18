from django.urls import path
from .consumers import AvisosEstudianteConsumer

websocket_urlpatterns = [path('ws/avisos/estudiante/', AvisosEstudianteConsumer.as_asgi())]
