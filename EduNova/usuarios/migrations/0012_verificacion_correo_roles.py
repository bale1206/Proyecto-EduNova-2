"""Desafíos OTP de personal académico: no modifica cuentas existentes."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0011_verificacion_correo_estudiantes')]

    operations = [
        migrations.CreateModel(
            name='VerificacionCorreoRol',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo_hash', models.CharField(max_length=255)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('enviado_en', models.DateTimeField()),
                ('vence_en', models.DateTimeField()),
                ('intentos_restantes', models.PositiveSmallIntegerField(default=5)),
                ('envios_ventana', models.PositiveSmallIntegerField(default=1)),
                ('inicio_ventana', models.DateTimeField()),
                ('confirmado_en', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='verificacion_correo_rol', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Verificación de correo de personal académico', 'verbose_name_plural': 'Verificaciones de personal académico'},
        ),
    ]
