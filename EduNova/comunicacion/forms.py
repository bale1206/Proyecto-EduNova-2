from django import forms

from academico.models import Curso
from usuarios.models import Usuario

from .models import MensajeComunicacion


class ComunicadoForm(forms.ModelForm):
    destinatario = forms.ModelChoiceField(
        queryset=Usuario.objects.none(), required=False,
        label='Destinatario individual (opcional)',
        help_text='Déjalo vacío si vas a enviar a todo un curso.',
    )
    curso_destino = forms.ModelChoiceField(
        queryset=Curso.objects.none(), required=False,
        label='Curso destino (opcional)',
    )

    class Meta:
        model = MensajeComunicacion
        fields = [
            'destinatario', 'curso_destino', 'asunto', 'cuerpo_mensaje',
            'tipo_comunicacion', 'archivo_adjunto', 'copia_utp_direccion',
            'requiere_firma_digital', 'exige_recibo_lectura',
        ]
        widgets = {
            'cuerpo_mensaje': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

        input_classes = (
            'w-full rounded-lg border px-3 py-2 text-sm focus:outline-none '
            'focus:ring-2 focus:ring-offset-0'
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput,)):
                field.widget.attrs.update({'class': 'rounded'})
            else:
                field.widget.attrs.update({'class': input_classes, 'style': 'border-color: var(--linea);'})

        if usuario and usuario.rol == Usuario.Rol.DOCENTE:
            # Un docente puede escribir a apoderados de sus cursos o a todo el curso
            self.fields['destinatario'].queryset = Usuario.objects.filter(
                rol=Usuario.Rol.APODERADO,
                estudiantes_a_cargo__curso__docente_jefe=usuario,
            ).distinct()
            self.fields['curso_destino'].queryset = Curso.objects.filter(docente_jefe=usuario)
        elif usuario and usuario.rol == Usuario.Rol.APODERADO:
            # Un apoderado puede escribir al/los docente(s) jefe de sus estudiantes
            self.fields['destinatario'].queryset = Usuario.objects.filter(
                rol=Usuario.Rol.DOCENTE,
                cursos_a_cargo__estudiantes__apoderado=usuario,
            ).distinct()
            self.fields['curso_destino'].widget = forms.HiddenInput()
            self.fields.pop('copia_utp_direccion', None)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('destinatario') and not cleaned.get('curso_destino'):
            raise forms.ValidationError('Debes elegir un destinatario individual o un curso.')
        return cleaned
