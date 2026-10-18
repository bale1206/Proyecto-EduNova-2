# Auditoría de uso de tablas

La condición solicitada fue eliminar tablas que no tuvieran una función directa o indirecta. Se revisaron los modelos, rutas, formularios, administración, servicios y las dos bases SQLite incluidas. No se identificaron tablas que cumplieran esa condición.

| Modelo / grupo | Función asociada |
| --- | --- |
| Usuario | Registro, autenticación, roles, sección principal y dirección de carrera. |
| Carrera | Director, ficha del estudiante, catálogo y análisis de asistencia. |
| Asignatura | Catálogo para crear secciones y filtrar análisis. |
| CarreraAsignatura | Malla curricular y filtro carrera → asignaturas; conserva referencias de la malla. |
| Curso | Secciones, docentes, matrículas, eventos, observaciones y asistencia. |
| Estudiante | Ficha, RUT, matrículas, observaciones y destinatario de los avisos. |
| Estudiante.secciones / Curso.docentes | Tablas intermedias de matrícula múltiple y docencia de secciones. |
| SesionClase | Una lista por sección y día. |
| MarcaAsistencia | Estado por estudiante; correcciones y porcentajes del análisis. |
| AvisoAsistencia | Avisos persistentes que se muestran al estudiante y se entregan por WebSocket. |
| RegistroAsistencia | Registro histórico, consulta desde Django Admin y respaldo vinculado a la sección en el formulario nuevo. Sus datos previos se importan al análisis. |
| Asistencia | Estados escolares históricos, fechas y justificativos, consulta desde administración/pantallas previas e importación al análisis. |
| ObservacionComportamiento y su tabla de estudiantes | Observaciones actuales, sanciones, resolución y avisos al estudiante. |
| Observacion | Historial individual, confidencialidad, consulta de ficha y administración/CSV. |
| Evento | Calendarios y actividades por sección. |
| TareaEstudio | Planificación privada del estudiante. |
| JustificacionRetiro | Solicitudes y documentos históricos, pantalla previa y revisión en administración. |
| MensajeComunicacion | Bandeja, comunicados, campana y avisos de observaciones. |
| PermisoTablaCSV | Configuración de importación y exportación por tabla. |
| Tablas de Django | Migraciones, usuarios/grupos/permisos, tipos de contenido, sesiones y registro de acciones del administrador. |

Las tablas con información histórica se mantienen, aunque su función actual sea indirecta. Eliminarlas supondría perder estados, justificativos, documentos o vínculos que no están completamente representados en las tablas nuevas.

La base dentro de academico/db.sqlite3 es un archivo duplicado independiente, no una tabla adicional de la base activa. La configuración utiliza la base de la raíz o PostgreSQL según .env. Ninguna de las copias de bases de datos se incluye en la entrega de código.
