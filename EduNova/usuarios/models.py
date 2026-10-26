from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.core.exceptions import ValidationError


class UsuarioManager(BaseUserManager):
    """
    Manager propio porque cambiamos el identificador de acceso de
    'username' a 'rut'. El UserManager por defecto de Django asume
    literalmente un parámetro llamado 'username', así que hay que
    reescribir create_user/create_superuser para que reciban 'rut'.
    """
    use_in_migrations = True

    def _crear_usuario(self, rut, email, password, **extra_fields):
        if not rut:
            raise ValueError('El RUT es obligatorio.')
        usuario = self.model(rut=rut, email=self.normalize_email(email), **extra_fields)
        usuario.password = make_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, rut, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._crear_usuario(rut, email, password, **extra_fields)

    def create_superuser(self, rut, email=None, password=None, **extra_fields):
        # El único rol permitido para un superusuario es "administrador":
        # no se pregunta ni se acepta otro valor.
        extra_fields['rol'] = Usuario.Rol.ADMINISTRADOR
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self._crear_usuario(rut, email, password, **extra_fields)


class Usuario(AbstractUser):
    """
    Extiende AbstractUser para representar la tabla Usuario del esquema.
    El identificador de acceso es el RUT (USERNAME_FIELD = 'rut'), no el
    username genérico que trae AbstractUser por defecto.

    Roles:
      - docente
      - apoderado
      - administrativo: directores y encargados de asignar cursos,
        evaluaciones, reuniones, etc. No se ofrece en el registro público
        por ahora (se crea desde /admin/ por un administrador); se agrega
        para dejar el modelo listo cuando se defina el flujo de creación.
      - administrador: rol exclusivo de los superusuarios del sistema. Se
        asigna automáticamente al crear un superusuario (manage.py
        createsuperuser) y no puede elegirse de otra forma.
    """

    class Rol(models.TextChoices):
        DOCENTE = 'docente', 'Docente'
        APODERADO = 'apoderado', 'Apoderado'
        ESTUDIANTE = 'estudiante', 'Estudiante'
        ADMINISTRATIVO = 'administrativo', 'Administrativo'
        ADMINISTRADOR = 'administrador', 'Administrador'

    # Roles que puede elegir cualquier persona en el registro público
    ROLES_ACTIVOS = (Rol.DOCENTE, Rol.ESTUDIANTE)

    rut = models.CharField('RUT', max_length=12, unique=True)
    apellidos = models.CharField('Apellidos', max_length=50)
    rol = models.CharField(max_length=30, choices=Rol.choices)
    telefono = models.CharField('Teléfono', max_length=15, blank=True)
    carrera_dirigida = models.ForeignKey(
        'academico.Carrera', on_delete=models.PROTECT, null=True, blank=True,
        related_name='directores', verbose_name='Carrera dirigida',
        help_text='Solo para directores de carrera; una carrera por director.',
    )
    asignaturas_asociadas = models.ManyToManyField(
        'academico.Asignatura', blank=True, related_name='docentes_asociados',
        limit_choices_to={'activa': True}, verbose_name='Asignaturas asociadas (docente)',
    )
    curso = models.ForeignKey(
        'academico.Curso', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usuarios_estudiantes', verbose_name='Curso',
        help_text='Campo histórico, no se usa en el registro de cuentas.',
    )

    objects = UsuarioManager()

    USERNAME_FIELD = 'rut'
    REQUIRED_FIELDS = ['email', 'first_name', 'apellidos']

    def clean(self):
        super().clean()
        if self.carrera_dirigida_id and self.rol != self.Rol.ADMINISTRATIVO:
            raise ValidationError({'carrera_dirigida': 'Solo un director de carrera puede tener una carrera asignada.'})
        if self.rol == self.Rol.ESTUDIANTE:
            from academico.models import Estudiante
            conflicto = Estudiante.objects.filter(rut_estudiante=self.rut).exclude(usuario_id=self.pk).exclude(usuario__isnull=True)
            if conflicto.exists():
                raise ValidationError({'rut': 'Este RUT ya está vinculado a otra cuenta de estudiante.'})

    def save(self, *args, **kwargs):
        # El campo 'username' heredado de AbstractUser sigue existiendo
        # (es unique=True a nivel de BD); lo mantenemos sincronizado con
        # el rut para que nunca quede vacío ni choque entre usuarios.
        self.username = self.rut
        using = kwargs.get('using') or self._state.db or 'default'
        with transaction.atomic(using=using):
            super().save(*args, **kwargs)
            relevantes = {'rol', 'rut', 'first_name', 'apellidos'}
            if self.rol == self.Rol.ESTUDIANTE and (kwargs.get('update_fields') is None or relevantes.intersection(kwargs['update_fields'])):
                from academico.models import Estudiante
                perfiles = Estudiante.objects.using(using)
                perfil = perfiles.filter(usuario_id=self.pk).first()
                if perfil is None:
                    perfil = perfiles.filter(rut_estudiante=self.rut, usuario__isnull=True).first()
                if perfil is None:
                    perfil = Estudiante(usuario=self, rut_estudiante=self.rut)
                perfil.usuario = self
                perfil.rut_estudiante = self.rut
                perfil.nombre_completo = self.nombre_completo or self.rut
                # La matrícula académica se administra separadamente de la cuenta.
                # No modificar la matrícula ni el curso histórico desde el registro.
                perfil.save(using=using)

    @property
    def codigo_edunova(self):
        """Código estable para docentes y apoderados, sin cambiar la PK interna."""
        from .codigos import crear_codigo
        tipo = {'docente': 'D', 'estudiante': 'A'}.get(self.rol)
        return crear_codigo(tipo, self.pk) if tipo else ''

    @property
    def nombre_completo(self):
        return f"{self.first_name} {self.apellidos}".strip()

    def es_docente(self):
        return self.rol == self.Rol.DOCENTE

    def es_estudiante(self):
        return self.rol == self.Rol.ESTUDIANTE

    def es_administrativo(self):
        return self.rol == self.Rol.ADMINISTRATIVO

    def es_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR

    def __str__(self):
        return f"{self.nombre_completo} ({self.get_rol_display()})"

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
