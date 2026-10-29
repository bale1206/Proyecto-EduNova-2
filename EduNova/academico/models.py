from django.conf import settings
from django.db import models, transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.db.models.functions import Substr, Length

from .secciones import prefijo_asignatura, validar_asignatura, validar_seccion, siguiente_numero

Usuario = settings.AUTH_USER_MODEL


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


class MencionCarrera(models.Model):
    """Mención perteneciente a una carrera. Puede existir más de una por carrera."""
    carrera = models.ForeignKey(Carrera, on_delete=models.PROTECT, related_name='menciones')
    nombre = models.CharField(max_length=160)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Mención de carrera'
        verbose_name_plural = 'Menciones de carreras'
        ordering = ['carrera__nombre', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['carrera', 'nombre'], name='uq_mencion_carrera_nombre'),
        ]

    def __str__(self):
        return f'{self.nombre} · {self.carrera.nombre}'


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
    # NULL: asignatura común a todas las menciones de la carrera.
    mencion = models.ForeignKey(
        MencionCarrera, on_delete=models.PROTECT, null=True, blank=True,
        related_name='plan_asignaturas', verbose_name='Mención (opcional)',
        help_text='Deja vacío si la asignatura es común a todas las menciones.',
    )
    fuente_malla = models.URLField(blank=True)
    anio_plan = models.PositiveSmallIntegerField(null=True, blank=True, choices=[(i, f"{i}° año") for i in range(1, 5)], verbose_name="Año curricular")
    semestre_plan = models.PositiveSmallIntegerField(null=True, blank=True, choices=[(1, "Primer semestre"), (2, "Segundo semestre")], verbose_name="Semestre curricular")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['carrera', 'asignatura'], condition=models.Q(mencion__isnull=True),
                name='uq_carrera_asignatura_comun',
            ),
            models.UniqueConstraint(
                fields=['carrera', 'asignatura', 'mencion'],
                condition=models.Q(mencion__isnull=False), name='uq_carrera_asignatura_mencion',
            ),
        ]
        verbose_name = 'Asignatura de una carrera'
        verbose_name_plural = 'Mallas de carreras'

    def clean(self):
        super().clean()
        if self.mencion_id and self.carrera_id and self.mencion.carrera_id != self.carrera_id:
            raise ValidationError({'mencion': 'La mención debe pertenecer a la carrera de esta asignatura.'})


class Curso(models.Model):
    # Nombre histórico del modelo para conservar FK y tablas existentes en Supabase.
    # En la interfaz y Django Admin se gestiona exclusivamente como una sección.
    docentes = models.ManyToManyField(
        Usuario, blank=True, related_name='secciones_impartidas',
        limit_choices_to={'rol': 'docente'}, verbose_name='Docentes asignados',
    )
    periodo_academico = models.ForeignKey(
        'PeriodoAcademico', on_delete=models.PROTECT, null=True, blank=True,
        related_name='secciones', verbose_name='Período académico',
    )
    codigo_institucional = models.CharField(
        'Código de sección en Duoc UC', max_length=45, blank=True, db_index=True,
        help_text='Ej.: OCY1104-001D. El identificador interno se conserva.',
    )
    docentes_oferta = models.TextField('Docentes informados en la oferta', blank=True, help_text='Nombres oficiales; no equivalen a cuentas verificadas.')
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
            numero = siguiente_numero(type(self), self.asignatura, using)
            self.seccion = f"{prefijo}-{numero:03d}-{sufijo}"
            try:
                with transaction.atomic(using=using):
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if intento == 4 or not type(self).objects.using(using).filter(seccion__in=[self.seccion[:-1] + 'D', self.seccion[:-1] + 'V']).exists():
                    raise

    @property
    def codigo_visible(self):
        """Código publicado en la oferta, o el interno si no existe."""
        return self.codigo_institucional or self.seccion

    @property
    def asignatura_visible(self):
        """Nombre del catálogo institucional, sin perder compatibilidad histórica."""
        return self.asignatura_catalogo.nombre if self.asignatura_catalogo_id else self.asignatura

    @property
    def codigo_asignatura_visible(self):
        return self.asignatura_catalogo.codigo if self.asignatura_catalogo_id else ''

    def __str__(self):
        return f"{self.codigo_visible} · {self.asignatura_visible} ({self.get_turno_display()})"

    class Meta:
        verbose_name = 'Sección de asignatura'
        verbose_name_plural = 'Secciones de asignaturas'
        ordering = ['seccion']
        constraints = [
            models.UniqueConstraint(Substr('seccion', 1, Length('seccion') - 2), name='curso_correlativo_prefijo_unico'),
            models.UniqueConstraint(fields=['periodo_academico', 'asignatura_catalogo', 'codigo_institucional'], condition=models.Q(periodo_academico__isnull=False) & ~models.Q(codigo_institucional=''), name='uq_oferta_periodo_asig_codigo'),
        ]


class HorarioSeccion(models.Model):
    class Dia(models.IntegerChoices):
        LUNES = 1, 'Lunes'
        MARTES = 2, 'Martes'
        MIERCOLES = 3, 'Miércoles'
        JUEVES = 4, 'Jueves'
        VIERNES = 5, 'Viernes'
        SABADO = 6, 'Sábado'
        DOMINGO = 7, 'Domingo'

    seccion = models.ForeignKey(Curso, related_name='horarios', on_delete=models.CASCADE)
    dia_semana = models.PositiveSmallIntegerField(choices=Dia.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        verbose_name = 'Horario de sección'
        verbose_name_plural = 'Horarios de secciones'
        ordering = ['dia_semana', 'hora_inicio']
        constraints = [models.UniqueConstraint(fields=['seccion','dia_semana','hora_inicio'], name='uq_horario_seccion_inicio')]

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': 'El término debe ser posterior al inicio.'})

    def __str__(self):
        return f'{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}'


class Estudiante(models.Model):
    class Modalidad(models.TextChoices):
        DIURNO = 'diurno', 'Diurno'
        VESPERTINO = 'vespertino', 'Vespertino'

    modalidad = models.CharField(
        'Modalidad de estudio', max_length=12, choices=Modalidad.choices,
        blank=True, default='',
        help_text='Se define durante el registro. Los estudiantes antiguos pueden tenerla pendiente.',
    )

    class EstadoAvance(models.TextChoices):
        AL_DIA = 'al_dia', 'Al día'
        CON_RETRASO = 'con_retraso', 'Con retraso'

    anio_ingreso = models.PositiveSmallIntegerField('Año de ingreso', null=True, blank=True)
    anio_carrera = models.PositiveSmallIntegerField('Año de carrera', null=True, blank=True,
        choices=[(1, '1° año'), (2, '2° año'), (3, '3° año'), (4, '4° año')])
    estado_avance = models.CharField('Situación académica declarada', max_length=15,
        choices=EstadoAvance.choices, blank=True, default='')
    carrera = models.ForeignKey(Carrera, on_delete=models.SET_NULL, null=True, blank=True, related_name="estudiantes")
    mencion = models.ForeignKey(
        MencionCarrera, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='estudiantes', verbose_name='Mención de carrera',
    )
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
        if self.mencion_id and (not self.carrera_id or self.mencion.carrera_id != self.carrera_id):
            raise ValidationError({'mencion': 'Selecciona una mención de la carrera del estudiante.'})

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

    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos')
    carrera = models.ForeignKey('Carrera', on_delete=models.CASCADE, null=True, blank=True, related_name='eventos_planificacion')
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
    curso = models.ForeignKey('Curso', on_delete=models.SET_NULL, null=True)
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
    seccion = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_historicos')
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
    seccion = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name='sesiones_clase')
    seccion_original = models.CharField(max_length=300, blank=True, editable=False)
    fecha = models.DateField()
    docente = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='sesiones_clase')
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['seccion', 'fecha'], name='uq_sesion_seccion_fecha')]
        ordering = ['-fecha']

    def save(self, *args, **kwargs):
        if self.seccion_id:
            self.seccion_original = str(self.seccion)
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'seccion_original'}
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.seccion or self.seccion_original or "Sección eliminada"} · {self.fecha}' 


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
    estudiante = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='tareas_estudio')
    titulo = models.CharField(max_length=160)
    descripcion = models.TextField(blank=True)
    fecha_limite = models.DateField(null=True, blank=True)
    completada = models.BooleanField(default=False)
    seccion = models.ForeignKey('Curso', null=True, blank=True, on_delete=models.SET_NULL, related_name='tareas_estudiantes', verbose_name='Asignatura y sección')
    color = models.CharField(max_length=7, default='#4C849D')
    prioridad = models.CharField(max_length=5, choices=[('alta', 'Alta'), ('media', 'Media'), ('baja', 'Baja')], default='media')
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name='Hora de realización')
    repeticion = models.CharField(max_length=8, choices=[('ninguna','No repetir'),('diaria','Cada día'),('semanal','Cada semana'),('mensual','Cada mes')], default='ninguna')
    minutos_antes = models.PositiveSmallIntegerField(choices=[(0,'A la hora'),(5,'5 minutos antes'),(10,'10 minutos antes'),(15,'15 minutos antes'),(30,'30 minutos antes'),(60,'1 hora antes')], default=15)
    recordatorios_activos = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['completada', 'fecha_limite', '-creada_en']
        verbose_name = 'Tarea de estudio'
        verbose_name_plural = 'Tareas de estudio'

    def __str__(self):
        return self.titulo


class RecordatorioTarea(models.Model):
    tarea = models.ForeignKey(TareaEstudio, on_delete=models.CASCADE, related_name='recordatorios')
    estudiante = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='recordatorios_tareas')
    programado_para = models.DateTimeField()
    texto = models.CharField(max_length=300)
    leido = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tarea', 'programado_para'], name='uq_recordatorio_tarea_fecha')]
        ordering = ['-creado_en']



class PeriodoAcademico(models.Model):
    """Período histórico: las ofertas de diferentes semestres NO se sobrescriben."""
    anio = models.PositiveSmallIntegerField()
    semestre = models.PositiveSmallIntegerField(choices=[(1, 'Primer semestre'), (2, 'Segundo semestre')])
    sede = models.CharField(max_length=100, default='Antonio Varas')

    class Meta:
        ordering = ['-anio', '-semestre', 'sede']
        constraints = [models.UniqueConstraint(fields=['anio', 'semestre', 'sede'], name='uq_periodo_anio_semestre_sede')]
        verbose_name = 'Período académico'
        verbose_name_plural = 'Períodos académicos'

    def __str__(self):
        return f'{self.sede} · {self.anio}-{self.semestre}'


class PlanEstudio(models.Model):
    """Versión de malla por cohorte y mención. No cambia planes previos."""
    carrera = models.ForeignKey(Carrera, on_delete=models.PROTECT, related_name='planes_estudio')
    mencion = models.ForeignKey(MencionCarrera, on_delete=models.PROTECT, null=True, blank=True, related_name='planes_estudio')
    anio_ingreso = models.PositiveSmallIntegerField('Año de ingreso de la cohorte')
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['carrera__nombre', '-anio_ingreso']
        verbose_name = 'Versión de malla curricular'
        verbose_name_plural = 'Versiones de mallas curriculares'
        constraints = [
            models.UniqueConstraint(fields=['carrera', 'anio_ingreso'], condition=models.Q(mencion__isnull=True), name='uq_plan_comun_ingreso'),
            models.UniqueConstraint(fields=['carrera', 'mencion', 'anio_ingreso'], condition=models.Q(mencion__isnull=False), name='uq_plan_mencion_ingreso'),
        ]

    def clean(self):
        super().clean()
        if self.mencion_id and self.carrera_id and self.mencion.carrera_id != self.carrera_id:
            raise ValidationError({'mencion': 'La mención debe pertenecer a la carrera.'})

    def __str__(self):
        return f'{self.carrera} · {self.mencion or "Común"} · cohorte {self.anio_ingreso}'


class PlanAsignatura(models.Model):
    plan = models.ForeignKey(PlanEstudio, on_delete=models.CASCADE, related_name='asignaturas')
    asignatura = models.ForeignKey(Asignatura, on_delete=models.PROTECT, related_name='planes_versionados')
    anio_curricular = models.PositiveSmallIntegerField(choices=[(i, f'{i}° año') for i in range(1, 5)])
    semestre_curricular = models.PositiveSmallIntegerField(choices=[(1, 'Primero'), (2, 'Segundo')])

    class Meta:
        verbose_name = 'Asignatura en versión de malla'
        verbose_name_plural = 'Asignaturas de versiones de mallas'
        constraints = [models.UniqueConstraint(fields=['plan', 'asignatura'], name='uq_asignatura_version_malla')]


class ImportacionAcademica(models.Model):
    """Auditoría y ubicación PRIVADA de los archivos revisados por el equipo."""
    TIPO = [('malla', 'Malla curricular'), ('oferta', 'Oferta semestral')]
    ESTADO = [('aplicada', 'Aplicada'), ('pendiente', 'Pendiente de transcripción')]
    tipo = models.CharField(max_length=10, choices=TIPO)
    estado = models.CharField(max_length=12, choices=ESTADO)
    archivo_nombre = models.CharField(max_length=240)
    archivo_privado = models.CharField(max_length=120, blank=True)
    sha256 = models.CharField(max_length=64)
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='importaciones_academicas')
    creado_en = models.DateTimeField(auto_now_add=True)
    resumen = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Importación académica'
        verbose_name_plural = 'Importaciones académicas'

    def __str__(self):
        return f'{self.get_tipo_display()} · {self.archivo_nombre} · {self.creado_en:%d/%m/%Y}'
