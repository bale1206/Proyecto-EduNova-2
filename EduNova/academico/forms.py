from django import forms

from usuarios.models import Usuario

from .models import Curso, Evento, JustificacionRetiro, ObservacionComportamiento

INPUT_CLASSES = (
    'w-full rounded-lg border px-3 py-2 text-sm focus:outline-none '
    'focus:ring-2 focus:ring-offset-0'
)
INPUT_STYLE = 'border-color: var(--linea);'


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['grado_curso', 'docente_jefe']
        labels = {'grado_curso': 'Curso', 'docente_jefe': 'Docente jefe'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['docente_jefe'].queryset = Usuario.objects.filter(rol=Usuario.Rol.DOCENTE)
        self.fields['docente_jefe'].required = False
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ['curso', 'tipo', 'titulo', 'descripcion', 'fecha', 'hora_inicio', 'hora_fin']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})


class JustificacionRetiroForm(forms.ModelForm):
    """Formulario que llena el apoderado para justificar un retiro,
    inasistencia o atraso de un estudiante suyo. El estudiante y el
    apoderado se completan en la vista, no aquí; el estado de aprobación
    queda en "pendiente" por defecto y lo revisa quien el colegio defina
    (docente o administrativo) más adelante."""

    class Meta:
        model = JustificacionRetiro
        fields = ['tipo_solicitud', 'motivo_texto', 'archivo_certificado']
        labels = {
            'tipo_solicitud': 'Tipo de solicitud',
            'motivo_texto': 'Motivo',
            'archivo_certificado': 'Certificado o respaldo (opcional)',
        }
        widgets = {
            'motivo_texto': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})


class ObservacionForm(forms.ModelForm):
    class Meta:
        model = ObservacionComportamiento
        fields = ['curso', 'estudiantes', 'tipo_observacion', 'asunto', 'descripcion', 'resolucion']
        
        # Estilos compartidos para todos los inputs
        estilo_input = 'w-full bg-[#1a1a1a] border border-[#333333] rounded-md p-2.5 text-white focus:outline-none focus:border-gray-500'
        
        widgets = {
            'curso': forms.Select(attrs={'class': estilo_input}),
            'estudiantes': forms.SelectMultiple(attrs={'class': estilo_input, 'size': 4}),
            'tipo_observacion': forms.Select(attrs={'class': estilo_input}),
            'asunto': forms.TextInput(attrs={'class': estilo_input}),
            'descripcion': forms.Textarea(attrs={'rows': 5, 'class': estilo_input}),
            'resolucion': forms.Textarea(attrs={'rows': 3, 'class': estilo_input}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not user.groups.filter(name='Administrativo').exists():
            if 'resolucion' in self.fields:
                self.fields.pop('resolucion')

class ActualizarObservacionForm(forms.ModelForm):
    # Campo extra que no pertenece al modelo directamente
    notificar_apoderado = forms.BooleanField(
        required=False,
        label="Notificar al apoderado",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox h-5 w-5 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 cursor-pointer'
        })
    )

    class Meta:
        model = ObservacionComportamiento
        fields = ['tipo_observacion', 'estado', 'resolucion']
        
        estilo_input = 'w-full bg-[#1a1a1a] border border-[#333333] rounded-md p-2.5 text-white focus:outline-none focus:border-gray-500'
        
        widgets = {
            'tipo_observacion': forms.Select(attrs={'class': estilo_input}),
            'estado': forms.Select(attrs={'class': estilo_input}),
            'resolucion': forms.Textarea(attrs={'rows': 5, 'class': estilo_input, 'placeholder': 'Escribe la resolución o acciones tomadas...'}),
        }