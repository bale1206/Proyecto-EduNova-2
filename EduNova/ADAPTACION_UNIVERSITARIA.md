# EduNova — transición universitaria (borrador)

Cambios implementados:
- Catálogo de carreras de la sede Antonio Varas (datos de referencia obtenidos de https://www.duoc.cl/sedes/antonio-varas/).
- `Estudiante.carrera` opcional y `Estudiante.secciones` (M2M), con migración que preserva registros previos.
- Panel de dirección: carreras, asignación de carrera, matrículas por sección y creación de asignaturas/secciones.
- Panel docente: secciones impartidas, calendario filtrable solo entre las propias.
- Panel estudiante: calendario por asignaturas inscritas con filtro que sobrevive la navegación mensual.
- CSV: la tabla heredada de cursos queda oculta del panel y la tabla de carreras está disponible; columna `carrera_id` exportable/importable para estudiantes y ejemplos actualizados. **Las importaciones técnicas usan IDs reales**, mientras que el panel de dirección permite asignación sin conocer los IDs.

## Antes de iniciar
1. Resguardar base de datos Supabase y archivo `.env` privado.
2. Ejecutar `python manage.py migrate` para crear carreras y tabla intermedia de matrícula.
3. En Dirección, asociar cada estudiante con su carrera y matricularlo en sus secciones.
4. En Dirección, asignar docentes a las secciones; un docente puede aparecer en asignaturas usadas por distintas carreras.
5. En permisos CSV, habilitar explícitamente `academico_carrera` para mostrar su descarga e importación.
6. Probar calendarios de docente y estudiante en diferentes meses y secciones.

## Límites del prototipo
- Se conserva internamente `Curso` como modelo de **asignatura/sección**, sin cambiar su tabla PostgreSQL ni las relaciones de eventos ya existentes.
- La codificación automática de secciones mantiene el esquema actual (p.ej. `ING-000D`), no aún el código institucional `006D`.
- No se incorporó una tabla académica completa de planes de estudio, créditos ni períodos; requieren diseño posterior.
- La sincronización básica usa eventos asociados a la sección y estudiantes matriculados; no hay integración externa con Blackboard.
- El vínculo de carrera del estudiante es opcional para no perder registros heredados.
- Las vistas no modificadas de asistencia/observaciones aún presentan referencias de cursos y deben migrarse posteriormente.
- Se excluyen `.env`, `venv`, `db.sqlite3` y artefactos temporales del ZIP.
