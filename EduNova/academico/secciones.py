import re
import unicodedata

from django.core.exceptions import ValidationError


def prefijo_asignatura(nombre):
    normalizado = unicodedata.normalize('NFKD', nombre or '').encode('ascii', 'ignore').decode('ascii')
    return ''.join(letra for letra in normalizado.upper() if 'A' <= letra <= 'Z')[:3]


def validar_asignatura(nombre):
    if len(prefijo_asignatura(nombre)) < 3:
        raise ValidationError('La asignatura debe contener al menos tres letras.', code='asignatura_corta')


def validar_seccion(valor):
    if not re.fullmatch(r'[A-Z]{3}-(?:[0-9]{3}|[1-9][0-9]{3,})[DV]', valor or ''):
        raise ValidationError('La sección debe tener un formato como MAT-000D o MAT-001V.')
