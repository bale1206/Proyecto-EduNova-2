from django.conf import settings
from django.db import models

Usuario = settings.AUTH_USER_MODEL


class Curso(models.Model):
    grado_curso = models.CharField('Curso', max_length=50)
    docente_jefe = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cursos_a_cargo',
        limit_choices_to={'rol': 'docente'},
    )

    def __str__(self):
        return self.grado_curso

    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'
        ordering = ['grado_curso']


class Estudiante(models.Model):
    rut_estudiante = models.CharField('RUT del estudiante', max_length=12, unique=True)
    nombre_completo = models.CharField(max_length=150)
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, related_name='estudiantes')
    apoderado = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='estudiantes_a_cargo',
        limit_choices_to={'rol': 'apoderado'},
    )
    # Apellido paterno del alumno, usado para agrupar hermanos como "Familia X"
    apellido_familiar = models.CharField(max_length=50, blank=True)

    def save(self, *args, **kwargs):
        if not self.apellido_familiar and self.nombre_completo:
            partes = self.nombre_completo.strip().split()
            if len(partes) >= 2:
                self.apellido_familiar = partes[-2] if len(partes) >= 3 else partes[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_completo

    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'
        ordering = ['nombre_completo']


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = 'presente', 'Presente'
        AUSENTE = 'ausente', 'Ausente'
        ATRASO = 'atraso', 'Atraso'
        JUSTIFICADO = 'justificado', 'Justificado'

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='asistencias')
    fecha = models.DateField()
    porcentaje_asistencia_actual = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PRESENTE)
    registrado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='asistencias_registradas')

    class Meta:
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.estudiante} - {self.fecha} - {self.estado}"


class Observacion(models.Model):
    class Tipo(models.TextChoices):
        POSITIVA = 'positiva', 'Positiva'
        NEGATIVA = 'negativa', 'Negativa'
        ACADEMICA = 'academica', 'Académica'
        OTRA = 'otra', 'Otra'

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='observaciones')
    docente_o_inspector = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='observaciones_creadas')
    fecha = models.DateField(auto_now_add=True)
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.OTRA)
    contenido_texto = models.TextField()
    confidencial = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Observación'
        verbose_name_plural = 'Observaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.estudiante}"


class JustificacionRetiro(models.Model):
    class TipoSolicitud(models.TextChoices):
        RETIRO_ANTICIPADO = 'retiro_anticipado', 'Retiro anticipado'
        INASISTENCIA = 'inasistencia', 'Justificación de inasistencia'
        ATRASO = 'atraso', 'Justificación de atraso'

    class EstadoAprobacion(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        APROBADA = 'aprobada', 'Aprobada'
        RECHAZADA = 'rechazada', 'Rechazada'

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='justificaciones')
    apoderado = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='justificaciones_enviadas')
    tipo_solicitud = models.CharField(max_length=30, choices=TipoSolicitud.choices)
    motivo_texto = models.TextField()
    archivo_certificado = models.FileField(upload_to='justificaciones/', blank=True, null=True)
    estado_aprobacion = models.CharField(max_length=20, choices=EstadoAprobacion.choices, default=EstadoAprobacion.PENDIENTE)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Justificación de retiro'
        verbose_name_plural = 'Justificaciones de retiro'
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.get_tipo_solicitud_display()} - {self.estudiante}"


class Evento(models.Model):
    """
    Modelo sugerido (no venía en el esquema original) para alimentar el
    calendario de docentes y apoderados: evaluaciones, reuniones y clases.
    """
    class Tipo(models.TextChoices):
        CLASE = 'clase', 'Clase'
        EVALUACION = 'evaluacion', 'Evaluación'
        REUNION = 'reunion', 'Reunión'
        OTRO = 'otro', 'Otro'

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='eventos')
    creado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='eventos_creados')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CLASE)
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    fecha = models.DateField()
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['fecha', 'hora_inicio']

    def __str__(self):
        return f"{self.titulo} ({self.fecha})"
