from django.contrib import admin

from .models import MensajeComunicacion


@admin.register(MensajeComunicacion)
class MensajeComunicacionAdmin(admin.ModelAdmin):
    list_display = ('folio', 'asunto', 'remitente', 'destinatario', 'curso_destino', 'tipo_comunicacion', 'leido', 'fecha_hora_envio')
    list_filter = ('tipo_comunicacion', 'leido')
    search_fields = ('folio', 'asunto')
