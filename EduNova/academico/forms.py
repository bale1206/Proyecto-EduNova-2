from django import forms
from django.core.exceptions import ValidationError

from usuarios.models import Usuario

from .models import Carrera, Curso, Evento, ObservacionComportamiento

INPUT_CLASSES = (
    'w-full rounded-lg border px-3 py-2 text-sm focus:outline-none '
    'focus:ring-2 focus:ring-offset-0'
)
INPUT_STYLE = 'border-color: var(--linea);'


class CursoForm(forms.ModelForm):
    turno = forms.TypedChoiceField(
        choices=[('true', 'Diurno'), ('false', 'Vespertino')],
        coerce=lambda valor: valor == 'true', initial='true', label='Turno',
    )
    class Meta:
        model = Curso
        fields = ['asignatura_catalogo', 'turno', 'docente_jefe']
        labels = {'docente_jefe': 'Docente asignado', 'asignatura_catalogo': 'Asignatura del catálogo'}

    def clean(self):
        datos = super().clean()
        catalogo = datos.get('asignatura_catalogo')
        if catalogo:
            self.instance.asignatura = catalogo.nombre
        return datos

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['asignatura_catalogo'].required = False
            self.initial['turno'] = 'true' if self.instance.turno else 'false'
        if 'docente_jefe' in self.fields:
            self.fields['docente_jefe'].queryset = Usuario.objects.filter(rol=Usuario.Rol.DOCENTE)
        if not self.instance.pk:
            self.fields['asignatura_catalogo'].required = True
        if 'docente_jefe' in self.fields:
            self.fields['docente_jefe'].required = False
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})


class CrearSeccionForm(CursoForm):
    carrera = forms.ModelChoiceField(queryset=Carrera.objects.all(), label='Carrera')
    docentes = forms.ModelMultipleChoiceField(queryset=Usuario.objects.filter(rol='docente'), label='Docentes asignados')

    class Meta(CursoForm.Meta):
        fields = ['carrera', 'asignatura_catalogo', 'turno', 'docentes']

    def __init__(self, *args, user=None, **kwargs):
        from .models import Asignatura
        super().__init__(*args, **kwargs)
        carreras = Carrera.objects.all().order_by('escuela', 'nombre')
        self.fields['carrera'].queryset = carreras
        if not self.is_bound and not self.initial.get('carrera'):
            self.initial['carrera'] = carreras.values_list('pk', flat=True).first()
        carrera_id = self.data.get('carrera') if self.is_bound else self.initial.get('carrera')
        asignaturas = Asignatura.objects.filter(activa=True, carreras__in=carreras.filter(pk=carrera_id)).distinct() if str(carrera_id or '').isdigit() else Asignatura.objects.none()
        self.fields['asignatura_catalogo'].queryset = asignaturas
        if not self.is_bound and not self.initial.get('asignatura_catalogo'):
            self.initial['asignatura_catalogo'] = asignaturas.values_list('pk', flat=True).first()
        asignatura_id = self.data.get('asignatura_catalogo') if self.is_bound else self.initial.get('asignatura_catalogo')
        self.numero_seccion = ''
        self.codigo_seccion = ''
        self.error_numero = ''
        elegida = asignaturas.filter(pk=asignatura_id).first() if str(asignatura_id or '').isdigit() else None
        if elegida:
            from .secciones import siguiente_numero, prefijo_asignatura
            try:
                self.numero_seccion = f'{siguiente_numero(Curso, elegida.nombre):03d}'
                turno = self.data.get('turno') if self.is_bound else self.initial.get('turno', 'true')
                sufijo = 'D' if turno in (True, 'true') else 'V'
                self.codigo_seccion = f'{prefijo_asignatura(elegida.nombre)}-{self.numero_seccion}-{sufijo}'
            except ValidationError as exc:
                self.error_numero = '; '.join(exc.messages)
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})

    def clean(self):
        from .secciones import siguiente_numero
        datos = super().clean()
        asignatura = datos.get('asignatura_catalogo')
        if asignatura:
            siguiente_numero(Curso, asignatura.nombre)
        return datos

    def save(self, commit=True):
        obj = super().save(commit=False)
        docentes = self.cleaned_data['docentes']
        obj.docente_jefe = docentes.first()
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class CarreraForm(forms.ModelForm):
    class Meta:
        model = Carrera
        fields = ['nombre', 'escuela']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})


class AsignarCarreraForm(forms.Form):
    estudiante = forms.ModelChoiceField(queryset=None, label='Estudiante')
    carrera = forms.ModelChoiceField(queryset=None, label='Carrera')

    def __init__(self, *args, **kwargs):
        from .models import Estudiante
        super().__init__(*args, **kwargs)
        self.fields['estudiante'].queryset = Estudiante.objects.order_by('nombre_completo')
        self.fields['carrera'].queryset = Carrera.objects.filter(activa=True)
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})


class MatricularSeccionForm(forms.Form):
    estudiante = forms.ModelChoiceField(queryset=None, label='Estudiante')
    seccion = forms.ModelChoiceField(queryset=None, label='Asignatura y sección')

    def __init__(self, *args, **kwargs):
        from .models import Estudiante
        super().__init__(*args, **kwargs)
        self.fields['estudiante'].queryset = Estudiante.objects.order_by('nombre_completo')
        self.fields['seccion'].queryset = Curso.objects.order_by('asignatura', 'seccion')
        for field in self.fields.values():
            field.widget.attrs.update({'class': INPUT_CLASSES, 'style': INPUT_STYLE})


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        labels = {"curso": "Asignatura y sección"}
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


class ActividadAdministrativaForm(EventoForm):
    """La misma lista de secciones al mostrar la agenda y al guardar."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['curso'].queryset = Curso.objects.select_related('asignatura_catalogo').order_by('asignatura', 'seccion')
        self.fields['curso'].empty_label = 'Seleccionar asignatura y sección'
        self.fields['tipo'].choices = [(Evento.Tipo.REUNION, 'Reunión'), (Evento.Tipo.OTRO, 'Otro evento')]


class ObservacionForm(forms.ModelForm):
    class Meta:
        model = ObservacionComportamiento
        fields = ['curso', 'estudiantes', 'tipo_observacion', 'asunto', 'descripcion', 'resolucion']
        
        # Estilos compartidos: respetan el tema claro/oscuro del sitio.
        estilo_input = 'w-full rounded-lg border px-3 py-2 text-sm surface-control focus:outline-none focus:ring-2'
        
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

        if user:
            from django.db.models import Q
            from .models import Estudiante
            if user.rol == 'docente':
                self.fields['curso'].queryset = Curso.objects.filter(Q(docentes=user) | Q(docente_jefe=user)).distinct()
            curso_id = self.data.get('curso') if self.is_bound else self.instance.curso_id
            self.fields['estudiantes'].queryset = Estudiante.objects.filter(Q(secciones__pk=curso_id) | Q(curso_id=curso_id)).distinct() if str(curso_id or '').isdigit() else Estudiante.objects.none()
        if user and user.rol not in ('administrativo', 'administrador'):
            if 'resolucion' in self.fields:
                self.fields.pop('resolucion')

class ActualizarObservacionForm(forms.ModelForm):
    # Campo extra que no pertenece al modelo directamente
    notificar_apoderado = forms.BooleanField(
        required=False,
        label="Avisar al estudiante",
        widget=forms.CheckboxInput(attrs={
            'class': 'h-5 w-5 rounded cursor-pointer accent-[var(--rio)]'
        })
    )

    class Meta:
        model = ObservacionComportamiento
        fields = ['tipo_observacion', 'estado', 'resolucion']
        
        estilo_input = 'w-full rounded-lg border px-3 py-2 text-sm surface-control focus:outline-none focus:ring-2'
        
        widgets = {
            'tipo_observacion': forms.Select(attrs={'class': estilo_input}),
            'estado': forms.Select(attrs={'class': estilo_input}),
            'resolucion': forms.Textarea(attrs={'rows': 5, 'class': estilo_input, 'placeholder': 'Escribe la resolución o acciones tomadas...'}),
        }