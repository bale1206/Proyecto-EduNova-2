from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
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
    (estudiante, docente y director de carrera). El rol administrador
    solo se crea mediante manage.py createsuperuser.
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

    def clean_email(self):
        correo = self.cleaned_data['email'].strip().lower()
        if self.data.get('rol') == Usuario.Rol.ESTUDIANTE:
            if correo.rsplit('@', 1)[-1] != 'duocuc.cl':
                raise ValidationError('Para registrarte como estudiante utiliza un correo @duocuc.cl.')
            if Usuario.objects.filter(email__iexact=correo).exists():
                raise ValidationError('Este correo ya está registrado. Inicia sesión o contacta a soporte.')
        return correo

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


class UsuarioAdminCreationForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ('rut', 'first_name', 'apellidos', 'email', 'telefono', 'rol', 'carrera_dirigida')


class UsuarioAdminChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = '__all__'

