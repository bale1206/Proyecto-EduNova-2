"""Códigos visibles de EduNova; el ID numérico sigue siendo la clave interna."""
import re

CODIGO_RE = re.compile(r"^EN-([ADP])(\d+)$", re.IGNORECASE)


def crear_codigo(tipo, pk):
    if pk is None:
        return ""
    return f"EN-{tipo}{pk:04d}"


def leer_codigo(value, tipo):
    match = CODIGO_RE.fullmatch(str(value).strip())
    if match is None or match.group(1).upper() != tipo or int(match.group(2)) < 1:
        return None
    return int(match.group(2))
