"""Comprueba en modo lectura el esquema para eventos y tareas personales.

Ejecutar: python manage.py diagnosticar_eventos
No modifica tablas, columnas ni registros.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = 'Diagnostica migraciones y campos necesarios para guardar eventos personales (solo lectura).'

    def handle(self, *args, **options):
        fallos = []
        with connection.cursor() as cursor:
            existentes = set(connection.introspection.table_names(cursor))
            tablas = {
                'academico_evento': {
                    'curso_id': True, 'carrera_id': True, 'creado_por_id': True,
                    'tipo': False, 'titulo': False, 'fecha': False,
                },
                'academico_tareaestudio': {
                    'estudiante_id': False, 'seccion_id': True,
                    'titulo': False, 'fecha_limite': True, 'tipo_actividad': False,
                },
            }
            for tabla, columnas in tablas.items():
                if tabla not in existentes:
                    fallos.append(f'Falta la tabla {tabla}.')
                    continue
                descripcion = {
                    c.name: c for c in connection.introspection.get_table_description(cursor, tabla)
                }
                for columna, admite_null in columnas.items():
                    c = descripcion.get(columna)
                    if c is None:
                        fallos.append(f'Falta la columna {tabla}.{columna}.')
                    elif admite_null and c.null_ok is False:
                        fallos.append(f'{tabla}.{columna} no admite NULL; el calendario personal lo requiere.')
        aplicadas = MigrationRecorder(connection).applied_migrations()
        for numero in ('0020_planificacion_compartida', '0027_actividad_personal_calendario'):
            if ('academico', numero) not in aplicadas:
                fallos.append(f'Falta aplicar la migración academico.{numero}.')
        if fallos:
            for mensaje in fallos:
                self.stderr.write(self.style.ERROR('ERROR: ' + mensaje))
            raise CommandError('Esquema de calendario incompatible. Haz un respaldo y revisa migraciones con: python manage.py showmigrations academico')
        self.stdout.write(self.style.SUCCESS('OK: tablas, campos y migraciones de eventos y tareas compatibles.'))
