"""Validaciones de alta de cuentas. No modifica usuarios ya existentes.

RUT: número de 7 u 8 cifras y dígito verificador módulo 11.
El algoritmo verifica coherencia matemática, NO identidad real.
"""
import re


def validar_y_normalizar_rut(valor):
    """Devuelve el RUT canonizado o None si el formato/DV no son correctos."""
    texto = (valor or '').strip().upper()
    if not re.fullmatch(r'(?:[0-9]{7,8}|[0-9]{1,2}\.[0-9]{3}\.[0-9]{3})-[0-9K]', texto):
        return None
    numero, dv = texto.replace('.', '').split('-')
    if int(numero) <= 0:
        return None
    total = sum(int(digito) * factor for digito, factor in zip(numero[::-1], (2, 3, 4, 5, 6, 7) * 2))
    resto = 11 - (total % 11)
    esperado = '0' if resto == 11 else 'K' if resto == 10 else str(resto)
    return f'{numero}-{dv}' if dv == esperado else None


def password_minimo_registro(valor):
    """Regla visible en el medidor. Los validadores de Django siguen siendo obligatorios."""
    if not valor or len(valor) < 8:
        return False
    tipos = sum((
        any(c.islower() for c in valor),
        any(c.isupper() for c in valor),
        any(c.isdigit() for c in valor),
        any(not c.isalnum() and not c.isspace() for c in valor),
    ))
    return tipos >= 2
