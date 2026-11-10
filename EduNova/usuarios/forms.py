from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError

from .models import Usuario
from .validaciones_registro import validar_y_normalizar_rut, password_minimo_registro

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
            'apellidos': 'Apellido',
            'email': 'Correo electrónico',
            'telefono': 'Teléfono (opcional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos obligatorios independientemente del perfil elegido.
        for obligatorio in ('rut', 'first_name', 'apellidos', 'email'):
            self.fields[obligatorio].required = True
        self.fields['telefono'].required = False
        self.fields['rut'].widget.attrs['autocomplete'] = 'off'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'
        for name, field in self.fields.items():
            if name == 'rol':
                continue
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})

    def clean_email(self):
        correo = self.cleaned_data['email'].strip().lower()
        from django.conf import settings
        rol = self.data.get('rol')
        dominios = {
            Usuario.Rol.ESTUDIANTE: 'duocuc.cl',
            **getattr(settings, 'EDUNOVA_ROLE_EMAIL_DOMAINS', {
                Usuario.Rol.DOCENTE: 'profesor.duoc.cl',
                Usuario.Rol.ADMINISTRATIVO: 'duoc.cl',
            }),
        }
        esperado = dominios.get(rol)
        if esperado and correo.rsplit('@', 1)[-1] != esperado:
            raise ValidationError(f'Para este perfil utiliza tu correo @{esperado}.')
        if Usuario.objects.filter(email__iexact=correo).exists():
            raise ValidationError('Este correo ya está registrado. Inicia sesión o contacta a soporte.')
        return correo

    def clean_rut(self):
        rut = validar_y_normalizar_rut(self.cleaned_data['rut'])
        if rut is None:
            raise ValidationError('El RUT debe tener formato correcto y dígito verificador válido (módulo 11).')
        if Usuario.objects.filter(rut=rut).exists():
            raise ValidationError('Ya existe una cuenta registrada con ese RUT.')
        return rut

    def clean_password2(self):
        password = super().clean_password2()
        if password and not password_minimo_registro(password):
            raise ValidationError('Utiliza al menos 8 caracteres y combina dos tipos: minúsculas, mayúsculas, números o símbolos.')
        return password


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

