from django.db import migrations, models


class Migration(migrations.Migration):
    """Añade el año de ingreso sin destruir una columna ya existente.

    Algunas instalaciones de EduNova ya disponen de academico_estudiante.anio_ingreso
    aunque su migración anterior no la registrara en el estado de Django.
    PostgreSQL (Supabase): ADD COLUMN IF NOT EXISTS conserva los datos existentes.
    La operación de estado informa correctamente a Django de la existencia del campo.
    """

    dependencies = [
        ('academico', '0022_limpieza_modelo_escolar'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE "academico_estudiante" '
                        'ADD COLUMN IF NOT EXISTS "anio_ingreso" smallint NULL;'
                    ),
                    # No retirar un campo que pudo existir antes de esta migración.
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='estudiante',
                    name='anio_ingreso',
                    field=models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        verbose_name='Año de ingreso',
                    ),
                ),
            ],
        ),
    ]
