# Tareas programadas y recordatorios en EduNova

- Fecha y hora: indican cuándo empieza la tarea; el nombre de la columna histórica sigue siendo `fecha_limite` para preservar datos.
- Repetición: única, diaria, semanal o mensual. En repetición mensual, el día 31 se adapta al último día de meses cortos.
- Antes de guardar, la persona elige cuántos minutos de antelación desea: 0, 5, 10, 15, 30 o 60.
- Después de crear, la ventana solo pregunta **Sí / No** sobre recordatorios **internos**. Sin Web Push, permisos móviles ni controles de frecuencia de notificaciones.
- La campana muestra recordatorios pendientes de leer. Los avisos se generan una sola vez por ocurrencia, usando la restricción única existente.
- Una tarea repetida se representa por un mismo registro y sus ocurrencias en el calendario. Marcar como completada detiene **toda la serie**; eliminar borra toda la serie y sus avisos.
- Los avisos NO aparecen sin programar `python manage.py enviar_recordatorios` periódicamente. Para respetar los 5 minutos, ejecutar **cada minuto** con el programador de tareas del servidor. NO utilizar el polling de interfaz para ello.
- Si el usuario no tiene abierta la página, los avisos estarán en la campana al volver. No aparecerán en la barra del celular.
- Si antes estaban activadas preferencias antiguas de avisos, la migración conserva el sí/no como internos; elimina suscripciones Push y deja 15 minutos por defecto. Los avisos ya generados permanecen.
- Ejecutar backup de Supabase antes de `python manage.py migrate`.
- Limitación: el calendario expande ocurrencias, pero no permite marcar cada ocurrencia como terminada por separado; completar una tarea repetida completa toda la serie.
