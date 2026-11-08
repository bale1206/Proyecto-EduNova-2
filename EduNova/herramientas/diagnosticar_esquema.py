"""Auditoría de solo lectura de las tablas y columnas Django de EduNova.

Ejecutar desde la carpeta EduNova: python herramientas/diagnosticar_esquema.py
Usa la base configurada en .env; NO modifica datos ni tablas.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edunova_project.settings")

import django
django.setup()

from django.apps import apps
from django.db import connection

LABELS = {"usuarios", "academico", "comunicacion"}
problems = []
checked_models = 0

with connection.cursor() as cursor:
    tables = set(connection.introspection.table_names(cursor))
    for model in apps.get_models(include_auto_created=True):
        opts = model._meta
        if (opts.app_label not in LABELS or opts.proxy or not opts.managed):
            continue
        checked_models += 1
        table = opts.db_table
        if table not in tables:
            problems.append(f"Falta tabla: {table}")
            continue
        columns = {
            item.name
            for item in connection.introspection.get_table_description(cursor, table)
        }
        for field in opts.local_fields:
            if field.column and field.column not in columns:
                problems.append(
                    f"Falta columna {table}.{field.column} "
                    f"(campo Django: {field.name})"
                )

print(f"Base revisada: {connection.vendor} / modelos revisados: {checked_models}")
if problems:
    for problem in problems:
        print("ALERTA:", problem)
    raise SystemExit(1)
print("OK: no faltan tablas ni columnas de EduNova en el esquema consultado.")
