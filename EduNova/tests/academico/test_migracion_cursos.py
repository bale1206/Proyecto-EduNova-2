from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionCursosExistentesTests(TransactionTestCase):
    def test_preserva_cursos_fichas_y_asigna_secciones_y_curso_del_usuario(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anteriores = [('academico', '0007_sanciones_observaciones'), ('usuarios', '0002_rol_estudiante')]
        try:
            executor.migrate(anteriores)
            apps = executor.loader.project_state(anteriores).apps
            Curso = apps.get_model('academico', 'Curso')
            Usuario = apps.get_model('usuarios', 'Usuario')
            Estudiante = apps.get_model('academico', 'Estudiante')
            docente = Usuario.objects.create(rut='1-9', username='1-9', rol='docente')
            apoderado = Usuario.objects.create(rut='2-7', username='2-7', rol='apoderado')
            alumno = Usuario.objects.create(rut='3-5', username='3-5', rol='estudiante')
            curso = Curso.objects.create(grado_curso='1A', docente_jefe=docente)
            otro = Curso.objects.create(grado_curso='Matemática')
            perfil = Estudiante.objects.create(rut_estudiante=alumno.rut, usuario=alumno, curso=curso, apoderado=apoderado, nombre_completo='Alumno Anterior')
            executor = MigrationExecutor(connection)
            executor.migrate(finales)
            apps = executor.loader.project_state(finales).apps
            nuevo_curso = apps.get_model('academico', 'Curso').objects.get(pk=curso.pk)
            nuevo_usuario = apps.get_model('usuarios', 'Usuario').objects.get(pk=alumno.pk)
            nuevo_perfil = apps.get_model('academico', 'Estudiante').objects.get(pk=perfil.pk)
            self.assertEqual(nuevo_curso.asignatura, 'Curso 1A')
            self.assertEqual(nuevo_curso.seccion, 'CUR-000-D')
            self.assertIs(nuevo_curso.turno, True)
            self.assertEqual(nuevo_curso.docente_jefe_id, docente.pk)
            self.assertEqual(nuevo_usuario.curso_id, curso.pk)
            self.assertEqual(nuevo_perfil.curso_id, curso.pk)
            self.assertEqual(nuevo_perfil.apoderado_id, apoderado.pk)
            self.assertEqual(apps.get_model('academico', 'Curso').objects.get(pk=otro.pk).seccion, 'MAT-000-D')
        finally:
            MigrationExecutor(connection).migrate(finales)
