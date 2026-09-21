from datetime import date, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand

from academico.models import Asistencia, Curso, Estudiante, Evento, Observacion
from comunicacion.models import MensajeComunicacion
from usuarios.models import Usuario


class Command(BaseCommand):
    help = 'Crea datos de demostración: usuarios, cursos, estudiantes, eventos y mensajes.'

    def handle(self, *args, **options):
        docente, creado = Usuario.objects.get_or_create(
            rut='11111111-1', defaults=dict(
                first_name='Camila', apellidos='Reyes', email='camila.reyes@edunova.cl',
                telefono='+56911111111', rol=Usuario.Rol.DOCENTE,
            ))
        if creado:
            docente.set_password('edunova123')
            docente.save()

        apoderado, creado = Usuario.objects.get_or_create(
            rut='22222222-2', defaults=dict(
                first_name='Jorge', apellidos='Muñoz', email='jorge.munoz@correo.cl',
                telefono='+56922222222', rol=Usuario.Rol.APODERADO,
            ))
        if creado:
            apoderado.set_password('edunova123')
            apoderado.save()

        director, creado = Usuario.objects.get_or_create(
            rut='33333333-3', defaults=dict(
                first_name='Soledad', apellidos='Ibáñez', email='soledad.ibanez@edunova.cl',
                telefono='+56933333333', rol=Usuario.Rol.ADMINISTRATIVO,
            ))
        if creado:
            director.set_password('edunova123')
            director.save()

        curso, _ = Curso.objects.get_or_create(grado_curso='5° Básico A', docente_jefe=docente)

        est1, _ = Estudiante.objects.get_or_create(
            rut_estudiante='30111222-3', defaults=dict(
                nombre_completo='Martina Muñoz Soto', curso=curso, apoderado=apoderado,
            ))
        est2, _ = Estudiante.objects.get_or_create(
            rut_estudiante='30111223-1', defaults=dict(
                nombre_completo='Benjamín Muñoz Soto', curso=curso, apoderado=apoderado,
            ))

        hoy = date.today()
        Evento.objects.get_or_create(
            curso=curso, titulo='Clase de Matemática', tipo=Evento.Tipo.CLASE,
            fecha=hoy + timedelta(days=1), creado_por=docente,
        )
        Evento.objects.get_or_create(
            curso=curso, titulo='Prueba de Lenguaje', tipo=Evento.Tipo.EVALUACION,
            fecha=hoy + timedelta(days=5), creado_por=docente,
        )
        Evento.objects.get_or_create(
            curso=curso, titulo='Reunión de apoderados', tipo=Evento.Tipo.REUNION,
            fecha=hoy + timedelta(days=10), creado_por=docente,
        )

        for i in range(5):
            Asistencia.objects.get_or_create(
                estudiante=est1, fecha=hoy - timedelta(days=i),
                defaults=dict(estado=Asistencia.Estado.PRESENTE, porcentaje_asistencia_actual=96, registrado_por=docente),
            )

        Observacion.objects.get_or_create(
            estudiante=est1, docente_o_inspector=docente, tipo=Observacion.Tipo.POSITIVA,
            contenido_texto='Destacó ayudando a sus compañeros en el trabajo grupal de Ciencias.',
        )

        MensajeComunicacion.objects.get_or_create(
            remitente=docente, curso_destino=curso, asunto='Bienvenida al año escolar',
            defaults=dict(cuerpo_mensaje='Estimadas familias, damos inicio al año escolar...', tipo_comunicacion='general'),
        )

    help = (
        'Crea (o actualiza) un superusuario fijo para el equipo, con RUT y '
        'clave conocidos por todos. Pensado para que cada integrante, tras '
        'clonar el repo y correr migrate, tenga el mismo acceso a /admin/.'
    )

    # --- Ajusta estos datos a gusto del equipo ---
    RUT = '99999999-9'
    NOMBRE = 'Admin'
    APELLIDOS = 'EduNova'
    EMAIL = 'admin@edunova.cl'
    ROL = Usuario.Rol.ADMINISTRADOR  # el modelo exige un rol válido; no afecta los permisos de superusuario
    PASSWORD = 'edunova123'
    # ----------------------------------------------

    def handle(self, *args, **options):
        admin, creado = Usuario.objects.get_or_create(
            rut=self.RUT,
            defaults=dict(
                first_name=self.NOMBRE,
                apellidos=self.APELLIDOS,
                email=self.EMAIL,
                rol=self.ROL,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            ),
        )

        # Si ya existía (por ejemplo, creado sin permisos), nos aseguramos
        # de que quede como superusuario y con la clave correcta.
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        admin.set_password(self.PASSWORD)
        admin.save()

        accion = 'creado' if creado else 'actualizado'
        self.stdout.write(self.style.SUCCESS(
            f'Superusuario {accion} correctamente.\n'
            f'RUT   -> {self.RUT}\n'
            f'Clave -> {self.PASSWORD}'
        ))



        self.stdout.write(self.style.SUCCESS(
            'Datos de demostración creados.\n'
            'Docente      -> RUT 11111111-1 / clave edunova123\n'
            'Apoderado    -> RUT 22222222-2 / clave edunova123\n'
            'Administrativo -> RUT 33333333-3 / clave edunova123'
        ))
