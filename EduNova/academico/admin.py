from django.contrib import admin

from .models import Asistencia, Curso, Estudiante, Evento, JustificacionRetiro, Observacion


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('grado_curso', 'docente_jefe')


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'rut_estudiante', 'curso', 'apoderado', 'apellido_familiar')
    list_filter = ('curso',)
    search_fields = ('nombre_completo', 'rut_estudiante')


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'fecha', 'estado', 'porcentaje_asistencia_actual')
    list_filter = ('estado', 'fecha')


@admin.register(Observacion)
class ObservacionAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo', 'fecha', 'confidencial')
    list_filter = ('tipo', 'confidencial')


@admin.register(JustificacionRetiro)
class JustificacionRetiroAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo_solicitud', 'estado_aprobacion', 'creado_en')
    list_filter = ('estado_aprobacion', 'tipo_solicitud')


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'tipo', 'fecha', 'hora_inicio')
    list_filter = ('tipo', 'curso')
