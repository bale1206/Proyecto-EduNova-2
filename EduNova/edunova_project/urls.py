"""
URL configuration for edunova_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from usuarios.views import landing_view

from academico import importacion_vistas

urlpatterns = [
    path('admin/importaciones-academicas/', importacion_vistas.panel_importaciones, name='edunova_importaciones_admin'),
    path('admin/importaciones-academicas/plantilla/', importacion_vistas.plantilla_malla, name='edunova_importaciones_plantilla'),
    path('admin/importaciones-academicas/archivo/<int:pk>/', importacion_vistas.descargar_archivo_importado, name='edunova_importaciones_archivo'),
    path('admin/', admin.site.urls),
    path('', landing_view, name='landing'),
    path('cuentas/', include('usuarios.urls')),
    path('', include('academico.urls')),
    path('mensajes/', include('comunicacion.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

