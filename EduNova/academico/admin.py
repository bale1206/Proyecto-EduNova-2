from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

from usuarios.models import Usuario
from .forms import CursoForm

from .models import Asignatura, CarreraAsignatura, Asistencia, Carrera, Curso, Estudiante, Evento, JustificacionRetiro, Observacion, ObservacionComportamiento, RegistroAsistencia, SesionClase, MarcaAsistencia, AvisoAsistencia


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "escuela", "activa")
    list_filter = ("escuela", "activa")
    search_fields = ("nombre",)


class CarreraAsignaturaInline(admin.TabularInline):
    model = CarreraAsignatura
    extra = 0


@admin.register(Asignatura)
class AsignaturaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activa')
    search_fields = ('codigo', 'nombre')
    list_filter = ('activa',)
    inlines = [CarreraAsignaturaInline]


class SeccionAdminForm(CursoForm):
    docentes = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(rol='docente'),
        required=True, label='Docentes que imparten esta sección',
        widget=forms.SelectMultiple(attrs={'size': 7}),
    )

    class Meta(CursoForm.Meta):
        fields = ['asignatura_catalogo', 'turno', 'docentes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('docente_jefe', None)
        if self.instance.pk:
            docentes = self.instance.docentes.all()
            if not docentes.exists() and self.instance.docente_jefe_id:
                docentes = Usuario.objects.filter(pk=self.instance.docente_jefe_id)
            self.fields['docentes'].initial = docentes

    def save(self, commit=True):
        obj = super().save(commit=False)
        docentes = list(self.cleaned_data['docentes'])
        # Campo heredado para compatibilidad con código y relaciones antiguas.
        obj.docente_jefe = docentes[0]
        if commit:
            obj.save()
            obj.docentes.set(docentes)
            self.save_m2m()
        return obj


class EstudianteSeccionesForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = ['usuario', 'rut_estudiante', 'nombre_completo', 'carrera', 'secciones']
        widgets = {'secciones': forms.SelectMultiple(attrs={'size': 10})}

    def clean(self):
        data = super().clean()
        secciones = data.get('secciones')
        if not secciones:
            raise ValidationError('El estudiante debe estar inscrito en al menos una asignatura y sección.')
        carrera = data.get('carrera')
        if carrera and secciones.exclude(asignatura_catalogo__carreras=carrera).exists():
            raise ValidationError('Las asignaturas seleccionadas deben pertenecer a la carrera del estudiante.')
        self.instance.curso = secciones.order_by('pk').first()
        return data


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('seccion', 'asignatura_catalogo', 'turno', 'docentes_resumen')
    readonly_fields = ('seccion',)
    search_fields = ('seccion', 'asignatura')
    list_filter = ('turno',)
    form = SeccionAdminForm
    exclude = ('docente_jefe', 'asignatura')

    @admin.display(description='Docentes')
    def docentes_resumen(self, obj):
        return ', '.join(str(docente) for docente in obj.docentes.all()) or str(obj.docente_jefe or 'Sin asignar')


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('codigo_edunova', 'nombre_completo', 'rut_estudiante', 'carrera', 'secciones_resumen')
    list_filter = ('carrera', 'secciones')
    form = EstudianteSeccionesForm
    exclude = ('curso', 'apoderado', 'apellido_familiar')

    @admin.display(description='Asignaturas y secciones')
    def secciones_resumen(self, obj):
        return ', '.join(str(sec) for sec in obj.secciones.all()) or 'Sin matrícula'
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
    def add_view(self, request, form_url='', extra_context=None):
        from django.shortcuts import redirect
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return redirect('academico:tomar_asistencia')

    @admin.display(description='RUT')
    def rut(self, obj):
        return obj.estudiante.rut_estudiante

    @admin.display(description='Nombre completo')
    def nombre_completo(self, obj):
        return obj.estudiante.nombre_completo

    @admin.display(description='Ausente', boolean=True)
    def ausente(self, obj):
        return not obj.presente

    @admin.display(description='Fecha y hora')
    def fecha_registro(self, obj):
        from django.utils import timezone
        return timezone.localtime(obj.fecha).strftime('%H-%M--%d/%m/%Y')

    readonly_fields = ('estudiante', 'seccion', 'docente', 'presente', 'justificado', 'fecha')
    list_display = ('rut', 'nombre_completo', 'presente', 'ausente', 'fecha_registro')
    list_filter = ('presente', 'justificado', 'fecha', 'docente')
    search_fields = ('estudiante__nombre_completo', 'docente__first_name', 'docente__last_name')


@admin.register(SesionClase)
class SesionClaseAdmin(admin.ModelAdmin):
    list_display = ('seccion', 'fecha', 'docente', 'actualizada_en')
    list_filter = ('fecha', 'seccion')


@admin.register(MarcaAsistencia)
class MarcaAsistenciaAdmin(admin.ModelAdmin):
    list_display = ('sesion', 'estudiante', 'presente', 'actualizado_en')
    list_filter = ('presente',)


@admin.register(AvisoAsistencia)
class AvisoAsistenciaAdmin(admin.ModelAdmin):
    list_display = ('destinatario', 'creado_en', 'leido')
    list_filter = ('leido',)
    readonly_fields = ('destinatario', 'marca', 'texto', 'creado_en')
