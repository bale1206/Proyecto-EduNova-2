import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edunova_project.settings')
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

http_application = get_asgi_application()
from academico.routing import websocket_urlpatterns
application = ProtocolTypeRouter({
    'http': http_application,
    'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
