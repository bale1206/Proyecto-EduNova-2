from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Comando escolar obsoleto; retirado durante la limpieza universitaria."

    def handle(self, *args, **options):
        raise CommandError("seed_demo fue retirado: no crea datos escolares. Usa Django Admin para configurar carreras, asignaturas y secciones.")
