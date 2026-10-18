# Portal de estudiante (borrador)

- El registro público ahora ofrece **Estudiante** en lugar de Apoderado.
- El estudiante accede a `/academico/estudiante/` y administra sus propias tareas.
- `academico.Estudiante.usuario` permite asociar una cuenta autenticada a un registro académico existente. No se asignan automáticamente los registros anteriores a usuarios: deben vincularse explícitamente y comprobar identidad.
- `TareaEstudio` guarda títulos, fechas y estados en PostgreSQL/Supabase tras ejecutar `python manage.py migrate`.
- Se conservaron intencionalmente `Estudiante.apoderado`, los cursos y las vistas docentes/administrativas como **estructura legada de compatibilidad** para no romper funciones fuera del alcance. El cambio completo del esquema escolar a carreras/asignaturas/secciones requiere otra fase.
- Las cuentas existentes con rol `apoderado` NO se transforman automáticamente en estudiantes, porque podrían representar personas diferentes. Deben revisarse y migrarse explícitamente.
- No se añade sincronización universitaria por sección: aún no existe ese modelo.
- La plantilla de calendario muestra eventos del modelo escolar solamente cuando hay un registro vinculado con curso; no inventa asignaturas ni créditos.
- Mantén tu `.env` local fuera de ZIP/Git. Realiza respaldo de Supabase antes de migrar.
