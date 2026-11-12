"""Pruebas locales aisladas: no conectan con la base de datos configurada en .env.

Las migraciones históricas contienen SQL de PostgreSQL. Aquí se crean tablas
desde los modelos en SQLite; las migraciones deben validarse en PostgreSQL
de pruebas antes de desplegarlas.
"""
import os
from importlib.util import find_spec

os.environ.setdefault('DJANGO_SECRET_KEY', 'edunova-local-tests-only')
from .settings import *  # noqa: F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
MIGRATION_MODULES = {'usuarios': None, 'academico': None, 'comunicacion': None}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
if find_spec('whitenoise') is None:
    MIDDLEWARE = [m for m in MIDDLEWARE if m != 'whitenoise.middleware.WhiteNoiseMiddleware']
