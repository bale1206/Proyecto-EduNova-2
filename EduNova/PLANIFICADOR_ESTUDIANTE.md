# Planificador de EduNova (estudiantes)

## Cambios
- Calendario ampliable, tareas visibles por día, filtros de secciones conservados.
- Tareas con asignatura/sección de matrícula, color, prioridad y etiqueta accesible **❗ Alta prioridad**.
- Tras crear una tarea, pregunta si se desean avisos. Se permite no recibirlos, 24 h antes, 3 y 1 días antes, o diariamente los 3 días anteriores.
- Campana interna con contador de avisos no leídos.
- Web Push a móvil opcional (requiere HTTPS, instalar EduNova como app desde pantalla de inicio en iOS, claves VAPID, permisos y tareas programadas).
- No se generan avisos mientras se navega sin interacción. El comando se ejecuta por separado.

## Instalación
```powershell
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py runserver
```

## Programar notificaciones
Crear tarea en Task Scheduler (Windows), cron o sistema equivalente para lanzar, idealmente **cada hora**, `python manage.py enviar_recordatorios`. Los recordatorios se programan a las 09:00 en la zona horaria de Django. Sin esa ejecución periódica los avisos no se envían. La restricción única impide duplicarlos al volver a ejecutar el comando.

Para Web Push configurar `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_SUBJECT` (email real `mailto:...`) en `.env`. Para generar un par de claves VAPID, utiliza una herramienta confiable de generación de claves, sin compartir la clave privada. Si falta configuración, EduNova ofrece solamente campana interna. La aplicación del servidor debe usar HTTPS real para solicitar permisos de notificaciones, salvo localhost.

**Limitaciones**: la importación académica y los calendarios de otros perfiles no cambian. La prioridad alta no altera la frecuencia de avisos. Las tareas existentes quedan sin asignatura, prioridad media y sin avisos; no se pierden. No se ejecutaron migraciones contra Supabase aquí. Los recordatorios internos solo aparecen después de la siguiente ejecución del comando; Push requiere un dispositivo suscrito, permisos y VAPID válido.
