from django.contrib import admin

from .models import Asistencia, Curso, Estudiante, Evento, JustificacionRetiro, Observacion, ObservacionComportamiento, RegistroAsistencia, Usuario


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

@admin.register(ObservacionComportamiento)
class ObservacionComportamientoAdmin(admin.ModelAdmin):
    # Columnas que se mostrarán en el listado
    list_display = ('asunto', 'tipo_observacion', 'estado', 'docente', 'curso', 'fecha_creacion')
    
    # Opciones para filtrar en el panel lateral derecho
    list_filter = ('estado', 'tipo_observacion', 'curso', 'fecha_creacion')
    
    # Barra de búsqueda (busca por asunto, descripción o nombre del docente)
    search_fields = ('asunto', 'descripcion', 'docente__first_name', 'docente__last_name')
    
    # Campos que el administrador no debería editar manualmente
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')

@admin.register(JustificacionRetiro)
class JustificacionRetiroAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo_solicitud', 'estado_aprobacion', 'creado_en')
    list_filter = ('estado_aprobacion', 'tipo_solicitud')


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'tipo', 'fecha', 'hora_inicio')
    list_filter = ('tipo', 'curso')

@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'docente', 'fecha', 'presente', 'justificado')
    list_filter = ('presente', 'justificado', 'fecha', 'docente')
    search_fields = ('estudiante__nombre_completo', 'docente__first_name', 'docente__last_name')
