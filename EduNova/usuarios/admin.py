from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario
from .forms import UsuarioAdminCreationForm, UsuarioAdminChangeForm


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    add_form = UsuarioAdminCreationForm
    form = UsuarioAdminChangeForm
    list_display = ('codigo_edunova', 'rut', 'first_name', 'apellidos', 'rol', 'carrera_dirigida', 'email', 'is_staff')
    list_filter = ('rol', 'carrera_dirigida', 'is_staff', 'is_active')
    search_fields = ('rut', 'first_name', 'apellidos', 'email')
    ordering = ('apellidos',)
    fieldsets = (
        (None, {'fields': ('rut', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'apellidos', 'email', 'telefono', 'rol', 'carrera_dirigida')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('rut', 'first_name', 'apellidos', 'email', 'telefono', 'rol', 'carrera_dirigida', 'password1', 'password2'),
        }),
    )
