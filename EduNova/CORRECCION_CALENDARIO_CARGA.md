# Corrección del calendario y pantalla de carga

- `academico/views.py`: la vista `home_estudiante` responde solamente con `_calendario.html` a peticiones HTMX (`HX-Request: true`), evitando insertar repetidamente el portal completo al navegar entre meses.
- `templates/base.html`: indicador de carga con reloj de arena para navegación, formularios tradicionales y peticiones HTMX. Aparece tras 300 ms; se oculta al terminar o al restaurar una página.
- `static/css/edunova.css`: fondo difuminado y animación respetuosa de la preferencia de movimiento reducido.
- `academico/test_student_calendar.py`: casos de regresión para octubre, noviembre, diciembre y enero, más navegación normal.

No se modifican modelos ni migraciones. Conservar `.env` local para conectar con Supabase. Ejecutar `python manage.py test academico.test_student_calendar` en un entorno Django configurado con base de datos de pruebas.
