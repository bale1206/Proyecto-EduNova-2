from django.conf import settings
from django.db import models, transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.db.models.functions import Substr, Length

from .secciones import prefijo_asignatura, validar_asignatura, validar_seccion

Usuario = settings.AUTH_USER_MODEL


class PermisoTablaCSV(models.Model):
    tabla = models.CharField(max_length=150, unique=True)
    exportar = models.BooleanField(default=False)
    importar = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Permiso de tabla CSV'
        verbose_name_plural = 'Permisos de tablas CSV'


class Carrera(models.Model):
    """Catálogo de carreras de la sede; no vincula directamente al docente."""
    escuela = models.CharField(max_length=120)
    nombre = models.CharField(max_length=180, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['escuela', 'nombre']
        verbose_name = 'Carrera'
        verbose_name_plural = 'Carreras'

    def __str__(self):
        return self.nombre


class Asignatura(models.Model):
    """Catálogo institucional. Su mantenimiento corresponde a Django Admin."""
    codigo = models.CharField(max_length=24, unique=True)
    nombre = models.CharField(max_length=180)
    carreras = models.ManyToManyField(Carrera, through='CarreraAsignatura', related_name='asignaturas')
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre', 'codigo']
        verbose_name = 'Asignatura de catálogo'
        verbose_name_plural = 'Asignaturas de catálogo'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class CarreraAsignatura(models.Model):
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE, related_name='malla')
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE, related_name='planes')
    fuente_malla = models.URLField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['carrera', 'asignatura'], name='uq_carrera_asignatura')]
        verbose_name = 'Asignatura de una carrera'
        verbose_name_plural = 'Mallas de carreras'


class Curso(models.Model):
    # Nombre histórico del modelo para conservar FK y tablas existentes en Supabase.
    # En la interfaz y Django Admin se gestiona exclusivamente como una sección.
    docentes = models.ManyToManyField(
        Usuario, blank=True, related_name='secciones_impartidas',
        limit_choices_to={'rol': 'docente'}, verbose_name='Docentes asignados',
    )
    asignatura_catalogo = models.ForeignKey(Asignatura, null=True, blank=True, on_delete=models.PROTECT, related_name="secciones")
    asignatura = models.CharField('Asignatura', max_length=150, validators=[validar_asignatura])
    turno = models.BooleanField('Turno', default=True, choices=[(True, 'Diurno'), (False, 'Vespertino')])
    seccion = models.CharField('Sección', max_length=50, unique=True, editable=False, validators=[validar_seccion])
    docente_jefe = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cursos_a_cargo',
        limit_choices_to={'rol': 'docente'},
    )

    def clean(self):
        super().clean()
        validar_asignatura(self.asignatura)
        if self.seccion and self._state.adding:
            validar_seccion(self.seccion)
            if not self.seccion.startswith(prefijo_asignatura(self.asignatura) + '-') or self.seccion[-1] != ('D' if self.turno else 'V'):
                raise ValidationError('La sección no coincide con la asignatura y el turno.')

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or self._state.db or 'default'
        if self.asignatura_catalogo_id:
            self.asignatura = self.asignatura_catalogo.nombre
        validar_asignatura(self.asignatura)
        prefijo = prefijo_asignatura(self.asignatura)
        sufijo = 'D' if self.turno else 'V'
        anterior = type(self).objects.using(using).filter(pk=self.pk).first() if self.pk else None
        regenerar = not anterior or prefijo_asignatura(anterior.asignatura) != prefijo or anterior.turno != self.turno
        if not regenerar:
            # La sección no puede ser cambiada manualmente.
            self.seccion = anterior.seccion
            return super().save(*args, **kwargs)
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'seccion', 'asignatura', 'turno'}
        # La restricción única resuelve también las creaciones simultáneas.
        for intento in range(5):
            codigos = type(self).objects.using(using).filter(seccion__startswith=prefijo + '-').values_list('seccion', flat=True)
            numeros = [int(codigo[4:-1]) for codigo in codigos if codigo[4:-1].isdigit()]
            self.seccion = f"{prefijo}-{max(numeros, default=-1) + 1:03d}{sufijo}"
            try:
                with transaction.atomic(using=using):
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if intento == 4 or not type(self).objects.using(using).filter(seccion__in=[self.seccion[:-1] + 'D', self.seccion[:-1] + 'V']).exists():
                    raise

    def __str__(self):
        return f"{self.seccion} · {self.asignatura} ({self.get_turno_display()})"

    class Meta:
        verbose_name = 'Sección de asignatura'
        verbose_name_plural = 'Secciones de asignaturas'
        ordering = ['seccion']
        constraints = [
            models.UniqueConstraint(Substr('seccion', 1, Length('seccion') - 1), name='curso_correlativo_prefijo_unico'),
        ]


class Estudiante(models.Model):
    carrera = models.ForeignKey(Carrera, on_delete=models.SET_NULL, null=True, blank=True, related_name="estudiantes")
    secciones = models.ManyToManyField(Curso, blank=True, related_name="matriculados", verbose_name="Asignaturas / secciones inscritas")
    usuario = models.OneToOneField(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='perfil_estudiante', limit_choices_to={'rol': 'estudiante'},
        verbose_name='Cuenta de estudiante',
    )
    rut_estudiante = models.CharField('RUT del estudiante', max_length=12, unique=True)
    nombre_completo = models.CharField(max_length=150)
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, related_name='estudiantes')
    apoderado = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='estudiantes_a_cargo',
        limit_choices_to={'rol': 'apoderado'},
    )
    # Apellido paterno del alumno, usado para agrupar hermanos como "Familia X"
    apellido_familiar = models.CharField(max_length=50, blank=True)

    def clean(self):
        super().clean()
        if self.usuario_id:
            if self.usuario.rol != 'estudiante':
                raise ValidationError({'usuario': 'La cuenta vinculada debe tener rol estudiante.'})

    @property
    def codigo_edunova(self):
        """Código del alumno derivado de su PK estable en PostgreSQL."""
        from usuarios.codigos import crear_codigo
        return crear_codigo('A', self.pk)

    def save(self, *args, **kwargs):
        if not self.apellido_familiar and self.nombre_completo:
            partes = self.nombre_completo.strip().split()
            if len(partes) >= 2:
                self.apellido_familiar = partes[-2] if len(partes) >= 3 else partes[-1]
        with transaction.atomic(using=kwargs.get('using') or self._state.db or 'default'):
            super().save(*args, **kwargs)
            if self.usuario_id:
                from usuarios.models import Usuario as CuentaUsuario
                CuentaUsuario.objects.using(self._state.db).filter(pk=self.usuario_id, rol='estudiante').update(curso_id=self.curso_id)

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
        SANCION = 'sancion', 'Sanción'
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

class ObservacionComportamiento(models.Model):
    TIPO_OPCIONES = [
        ('SANCION', 'Sanción'),
        ('ESPECIALISTA', 'Requiere especialista'),
    ]

    ESTADO_OPCIONES = [
        ('NO_VISTA', 'No vista'),
        ('EN_PROCESO', 'En proceso'),
        ('RESUELTA', 'Resuelta'),
    ]

    # El ID se crea de forma automática e invisible por defecto en Django
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='observaciones_comportamiento_creadas'
    )
    asunto = models.CharField(max_length=200)
    tipo_observacion = models.CharField(max_length=20, choices=TIPO_OPCIONES)
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE)
    estudiantes = models.ManyToManyField('Estudiante') 
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_OPCIONES, default='NO_VISTA')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    administrativo = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='observaciones_modificadas'
    )
    resolucion = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.estado = 'NO_VISTA'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asunto} - {self.get_tipo_observacion_display()}"

class RegistroAsistencia(models.Model):
    # Al relacionar con Estudiante, accedemos automáticamente a su RUT, nombre y Apoderado
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='registros_asistencia')
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='registros_asistencia_docente')
    
    presente = models.BooleanField()
    justificado = models.BooleanField(default=False, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        estado = "Presente" if self.presente else "Ausente"
        return f"{self.estudiante.nombre_completo} - {estado} ({self.fecha.strftime('%H:%M - %d/%m/%Y')})"

    


class SesionClase(models.Model):
    """Una lista por sección y día. No se crean duplicados al corregirla."""
    seccion = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name='sesiones_clase')
    fecha = models.DateField()
    docente = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='sesiones_clase')
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['seccion', 'fecha'], name='uq_sesion_seccion_fecha')]
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.seccion} · {self.fecha}'


class MarcaAsistencia(models.Model):
    sesion = models.ForeignKey(SesionClase, on_delete=models.CASCADE, related_name='marcas')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.PROTECT, related_name='marcas_asistencia')
    presente = models.BooleanField()
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['sesion', 'estudiante'], name='uq_marca_sesion_estudiante')]


class AvisoAsistencia(models.Model):
    """Avisos privados persistentes; WebSocket solo avisa en tiempo real."""
    destinatario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='avisos_asistencia')
    marca = models.ForeignKey(MarcaAsistencia, on_delete=models.CASCADE, related_name='avisos')
    texto = models.CharField(max_length=250)
    creado_en = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    class Meta:
        ordering = ['-creado_en']


class TareaEstudio(models.Model):
    """Tarea privada, gestionada exclusivamente por su estudiante propietario."""
    estudiante = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='tareas_estudio', limit_choices_to={'rol': 'estudiante'})
    titulo = models.CharField(max_length=160)
    descripcion = models.TextField(blank=True)
    fecha_limite = models.DateField(null=True, blank=True)
    completada = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['completada', 'fecha_limite', '-creada_en']
        verbose_name = 'Tarea de estudio'
        verbose_name_plural = 'Tareas de estudio'

    def __str__(self):
        return self.titulo
