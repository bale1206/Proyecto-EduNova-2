import re
import unicodedata
from django.core.exceptions import ValidationError


def prefijo_asignatura(nombre):
    normalizado = unicodedata.normalize('NFKD', nombre or '').encode('ascii', 'ignore').decode('ascii')
    return ''.join(letra for letra in normalizado.upper() if 'A' <= letra <= 'Z')[:3]


def validar_asignatura(nombre):
    if len(prefijo_asignatura(nombre)) < 3:
        raise ValidationError('La asignatura debe contener al menos tres letras.')


def validar_seccion(valor):
    if not re.fullmatch(r'[A-Z]{3}-[0-9]{3}-[DV]', valor or ''):
        raise ValidationError('La sección debe tener un formato como MAT-000-D, entre 000 y 999.')


def siguiente_numero(modelo, nombre, using='default'):
    prefijo = prefijo_asignatura(nombre)
    codigos = modelo.objects.using(using).filter(seccion__startswith=prefijo + '-').values_list('seccion', flat=True)
    numeros = [int(codigo.split('-')[1]) for codigo in codigos if len(codigo.split('-')) == 3 and codigo.split('-')[1].isdigit()]
    numero = max(numeros, default=-1) + 1
    if numero > 999:
        raise ValidationError('Se agotaron los números de sección de este prefijo (000 a 999).')
    return numero
