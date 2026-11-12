# Horarios personales y registro simplificado

## Cambios

- Estudiantes, docentes y directores se registran con RUT, nombre, apellido,
  teléfono opcional, correo institucional y contraseña con confirmación.
  El tipo de cuenta se elige en el mismo formulario.
- Dominios: estudiantes `duocuc.cl`, docentes `profesor.duoc.cl`, directores
  `duoc.cl`. Ninguno de estos perfiles obtiene permisos de administrador.
- Los tres perfiles reciben un código de seis dígitos por correo antes de
  activar la cuenta. Al verificarlo entran automáticamente a su portal.
  El código dura diez minutos, admite cinco intentos y tiene reenvíos limitados.
- Se eliminan los datos académicos del registro y los selectores de carrera,
  asignatura y sección del calendario y de sus formularios de actividades.
  Los registros históricos de la base de datos se conservan.
- Estudiantes y docentes descargan una plantilla XLSX desde su calendario.
  La hoja `Horario` está vacía y la hoja `Ejemplo` contiene datos ficticios
  que no se importan. El archivo también incluye instrucciones.
- El horario es privado e independiente de carreras, asignaturas y matrículas
  del catálogo. Las asignaturas importadas son nombres en el horario personal.
- Una fila representa un bloque semanal con asignatura, día, hora de inicio,
  hora de término, fechas de inicio y término, sala y docente opcionales.
  Se aceptan fechas/horas de Excel o fechas `AAAA-MM-DD` y horas `HH:MM`.
- La revisión no escribe en la base de datos. Al confirmar se reemplazan
  únicamente los bloques importados de la cuenta actual, en una transacción.
  Las tareas y eventos existentes no se eliminan. Se rechazan bloques repetidos,
  cruces de horario, fórmulas, archivos incompatibles y filas incompletas.
- Máximos: 5 MB, 300 bloques y 370 días por bloque, entre 2000 y 2199.
  No se admiten bloques que crucen medianoche.
- El calendario muestra todos los bloques y sus horas, únicamente en los días
  y fechas de vigencia definidos. Permite navegar entre meses sin recargar
  toda la página. En móviles se desplaza horizontalmente dentro del calendario.
- Las nuevas reuniones, evaluaciones y eventos son personales y ya no se
  publican mediante catálogos de carreras/secciones. Dirección conserva las
  opciones de reunión y evento. Las antiguas relaciones se conservan para
  administración e historial, pero no alimentan el nuevo calendario.
- Tipografía base de 20 px con opciones mayores de accesibilidad. Calendario
  a todo el ancho en escritorio, horas visibles y página principal actualizada.
- Tailwind compilado, HTMX y Alpine se sirven localmente; no necesitan CDN.
- Se mantiene la corrección del inicio del admin al sobrescribir el proyecto.
  También se corrige el formulario de contraseña para Django 6.

## Instalación y Render

1. Sustituir los archivos de `EduNova` en el repositorio. Conservar el `.env`,
   el entorno virtual y la base de datos de la instalación. El ZIP los excluye.
2. Instalar las dependencias de `requirements.txt` como se hace actualmente.
3. Aplicar las migraciones antes de atender peticiones:

   ```sh
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```

   La migración nueva es `academico.0028_horario_personal`. Crea una tabla y
   restricciones de validación; no borra ni modifica los catálogos históricos.

4. En Render se puede mantener el comando de construcción actual:

   ```sh
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```

   Configurar `python manage.py migrate --noinput` como comando previo al
   despliegue, si el servicio lo permite. Como alternativa, utilizar este comando
   de inicio para aplicar las migraciones antes de arrancar Daphne:

   ```sh
   python manage.py migrate --noinput && daphne -b 0.0.0.0 -p $PORT edunova_project.asgi:application
   ```

5. Publicar el cambio en GitHub y desplegar. No se ha modificado el repositorio
   remoto ni el servicio de Render desde esta entrega.

## Correo de verificación

Se utiliza la configuración SMTP que ya empleaban los estudiantes. Para envío
real, `EMAIL_BACKEND` debe ser `django.core.mail.backends.smtp.EmailBackend`.
Configurar `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL` según el proveedor.
No activar TLS y SSL simultáneamente. El backend de consola no envía códigos
y el formulario informa de la falta de configuración sin crear una cuenta.

La antigua bandera `EDUNOVA_ROLE_OTP_READY` y el modo de demostración con Gmail
ya no controlan el registro. Los dominios institucionales se validan en servidor.
No se han probado entregas reales de correo desde este entorno.

## Validación

Se ejecutaron 62 pruebas de los flujos afectados: registro básico, dominios,
activación de los tres perfiles, vencimiento y límites del código, fallos SMTP,
importación con revisión, cruces y duplicados, privacidad, reemplazo atómico,
plantilla real, calendario, acceso al admin y retirada de su importador.

Comando reproducible para esas pruebas locales aisladas:

```sh
python manage.py test tests.usuarios.test_acceso_admin tests.academico.test_importacion_academica tests.academico.test_horario_personal tests.usuarios.test_registro_simple tests.usuarios.test_verificacion_estudiante tests.usuarios.test_verificacion_roles tests.usuarios.test_validaciones_registro tests.academico.test_modalidad_registro tests.academico.test_menciones_registro tests.academico.test_creacion_calendario_roles tests.academico.test_student_calendar --settings=edunova_project.settings_test
```

`settings_test` usa SQLite en memoria y crea las tablas desde los modelos, sin
ejecutar las migraciones históricas específicas de PostgreSQL. Nunca conecta
con la base de datos de `.env`. La validación de migraciones en PostgreSQL de
pruebas y del despliegue real queda a cargo de la instalación.

Se comprobó `makemigrations --check --dry-run` sin cambios pendientes. Se revisó
el calendario en Edge a 1440 px y 390 px: texto base de 20 px, navegación mensual,
ausencia de selectores académicos y sin desbordamiento horizontal de la página.
Las regresiones de los selectores académicos se actualizaron para verificar
su retirada. Los modelos y utilidades de catálogo históricos se conservan.

## Estilos y dependencias locales

El CSS de utilidades está compilado y no requiere Node para desplegar Django.
Para regenerarlo al cambiar clases de Tailwind, usar Tailwind CSS 3.4.17:

```sh
tailwindcss -c herramientas/tailwind.config.cjs -i static/css/tailwind.input.css -o static/css/utilidades.css --minify
```

Dependencias redistribuidas: HTMX 1.9.12 (0BSD), Alpine.js 3.14.1 (MIT) y Tailwind
CSS 3.4.17 (MIT). Los avisos de licencia están en `static/vendor`.
