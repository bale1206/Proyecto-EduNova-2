from django import forms

from usuarios.models import Usuario

from .models import Curso, Evento

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
