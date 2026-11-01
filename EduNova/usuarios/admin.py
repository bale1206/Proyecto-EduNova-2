from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import Usuario, VerificacionCorreoRol
from .forms import UsuarioAdminCreationForm, UsuarioAdminChangeForm


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    add_form = UsuarioAdminCreationForm
    form = UsuarioAdminChangeForm
    list_display = ('codigo_edunova', 'rut', 'first_name', 'apellidos', 'rol', 'carrera_dirigida', 'email', 'asignaturas', 'is_staff')
    list_filter = ('rol', 'carrera_dirigida', 'is_staff', 'is_active')
    search_fields = ('rut', 'first_name', 'apellidos', 'email')
    ordering = ('apellidos',)
    fieldsets = (
        (None, {'fields': ('rut', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'apellidos', 'email', 'telefono', 'rol', 'carrera_dirigida', 'carreras_dirigidas', 'carreras_docencia', 'menciones_docencia', 'asignaturas_asociadas')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('rut', 'first_name', 'apellidos', 'email', 'telefono', 'rol', 'carrera_dirigida', 'password1', 'password2'),
        }),
    )

    @admin.display(description='Asignaturas del estudiante')
    def asignaturas(self, obj):
        if obj.rol != 'estudiante':
            return '—'
        from academico.models import Estudiante
        perfil = Estudiante.objects.filter(usuario=obj).first()
        if not perfil:
            return 'Sin ficha'
        return format_html('<a href="{}">Asignar asignaturas / secciones</a>', reverse('admin:academico_estudiante_change', args=[perfil.pk]))


@admin.register(VerificacionCorreoRol)
class VerificacionCorreoRolAdmin(admin.ModelAdmin):
    """Historial de códigos enviados a docentes y directores; sin aprobación manual."""
    list_display = ('usuario', 'correo', 'confirmado_en', 'vence_en', 'activo')
    list_filter = ('confirmado_en', 'usuario__rol')
    search_fields = ('usuario__rut', 'usuario__email')
    readonly_fields = ('usuario', 'codigo_hash', 'creado_en', 'enviado_en', 'vence_en',
                       'intentos_restantes', 'envios_ventana', 'inicio_ventana', 'confirmado_en')

    @admin.display(description='Correo')
    def correo(self, obj):
        return obj.usuario.email

    @admin.display(boolean=True, description='Activa')
    def activo(self, obj):
        return obj.usuario.is_active

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
