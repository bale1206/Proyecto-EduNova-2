# Planificación compartida — implementación

- Estudiantes: tareas personales existentes y eventos por sección + carrera matriculada.
- Docentes: tareas personales privadas, eventos compartidos por secciones asignadas y eventos generales de las carreras asociadas a dichas secciones.
- Directores: tareas privadas, publicación por sección de su carrera o publicación general de su carrera.
- Los cambios en eventos compartidos se consultan en la base de datos en cada visita/cambio de mes: sincronización al recargar/navegar, **no actualización WebSocket instantánea**.
- Para activar los avisos internos de tareas de cualquier perfil, ejecutar periódicamente `python manage.py enviar_recordatorios` (idealmente cada minuto).
- Aplicar `python manage.py migrate` para agregar `Evento.carrera` y ampliar propietarios de tareas.
- No se elimina ninguna tabla histórica ni las funciones existentes de asistencia/analítica. Se reemplazan solo las páginas iniciales de docente y director.
- El efecto lupa se abre con hover o foco de teclado sobre un día. En pantallas táctiles, el foco depende del navegador.
- No es un sistema de invitaciones o confirmación de asistencia a eventos; la visibilidad se determina por matrícula, sección y carrera.
