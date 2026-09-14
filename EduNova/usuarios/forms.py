from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Usuario

INPUT_CLASSES = (
    'w-full rounded-lg border px-3 py-2 text-sm focus:outline-none '
    'focus:ring-2 focus:ring-offset-0'
)
INPUT_STYLE = 'border-color: var(--linea);'


class RegistroForm(UserCreationForm):
    """
    Registro de cuenta. Solo se ofrecen los roles habilitados por ahora
    (docente y apoderado); 'administrativo' (directores, encargados de
    asignar cursos/evaluaciones/reuniones) y 'administrador' quedan fuera
    del choices: el primero se crea desde /admin/, el segundo solo existe
    vía manage.py createsuperuser.
    """
    rol = forms.ChoiceField(
        choices=[(r.value, r.label) for r in Usuario.ROLES_ACTIVOS],
        widget=forms.RadioSelect,
        label='Soy...',
    )

    class Meta:
        model = Usuario
        fields = ['rut', 'first_name', 'apellidos', 'email', 'telefono', 'rol']
        labels = {
            'first_name': 'Nombre',
            'apellidos': 'Apellidos',
            'email': 'Correo electrónico',
            'telefono': 'Teléfono',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'rol':
                continue
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})

    def clean_rut(self):
        rut = self.cleaned_data['rut'].strip().upper().replace('.', '')
        if Usuario.objects.filter(rut=rut).exists():
            raise ValidationError('Ya existe una cuenta registrada con ese RUT.')
        return rut


class LoginForm(forms.Form):
    rut = forms.CharField(label='RUT', max_length=12)
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})
