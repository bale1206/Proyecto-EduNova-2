import uuid

from django.conf import settings
from django.db import models

from academico.models import Curso

Usuario = settings.AUTH_USER_MODEL


class MensajeComunicacion(models.Model):
    class TipoComunicacion(models.TextChoices):
        GENERAL = 'general', 'Comunicado general'
        CITACION = 'citacion', 'Citación / Reunión'
        ACADEMICO = 'academico', 'Aviso académico'
        DISCIPLINARIO = 'disciplinario', 'Aviso disciplinario'
        RESPUESTA = 'respuesta', 'Respuesta directa'

    folio = models.CharField(max_length=50, unique=True, blank=True)
    remitente = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='mensajes_enviados')
    destinatario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, null=True, blank=True,
        related_name='mensajes_recibidos',
        help_text='Dejar vacío si el mensaje se envía a todo un curso.',
    )
    curso_destino = models.ForeignKey(
        Curso, on_delete=models.CASCADE, null=True, blank=True,
        related_name='mensajes',
        help_text='Usar para comunicar a todos los apoderados de un curso.',
    )
    asunto = models.CharField(max_length=150)
    cuerpo_mensaje = models.TextField()
    tipo_comunicacion = models.CharField(max_length=40, choices=TipoComunicacion.choices, default=TipoComunicacion.GENERAL)
    archivo_adjunto = models.FileField(upload_to='comunicados/', blank=True, null=True)
    copia_utp_direccion = models.BooleanField('Copia a UTP/Dirección', default=False)
    requiere_firma_digital = models.BooleanField(default=False)
    exige_recibo_lectura = models.BooleanField(default=False)
    fecha_hora_envio = models.DateTimeField(auto_now_add=True)

    # Campos de apoyo para la campana de notificaciones (no venían en el
    # esquema original pero son necesarios para saber qué está "sin leer").
    leido = models.BooleanField(default=False)
    fecha_lectura = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Mensaje / Comunicado'
        verbose_name_plural = 'Mensajes / Comunicados'
        ordering = ['-fecha_hora_envio']

    def save(self, *args, **kwargs):
        if not self.folio:
            self.folio = f"EN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.folio}] {self.asunto}"
