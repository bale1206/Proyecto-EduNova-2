# EduNova

Plataforma web de comunicación colegio-familia. Frontend con **HTMX + Alpine.js
+ Tailwind (CDN)**, backend con **Django**.

Estado del proyecto: es un **prototipo funcional** para mostrar a un cliente
potencial (aún no confirmado). Los datos son de ejemplo (`seed_demo`), no hay
integración con un colegio real todavía.

## Instalación

```bash
python3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo      # crea usuarios y datos de ejemplo
python manage.py runserver
```

Abrir http://127.0.0.1:8000/

## Usuarios de prueba (creados por `seed_demo`)

| Rol           | RUT          | Clave        |
|---------------|--------------|--------------|
| Docente       | 11111111-1   | edunova123   |
| Apoderado     | 22222222-2   | edunova123   |
| Administrativo| 33333333-3   | edunova123   |

Además, el `db.sqlite3` que se entrega ya trae un superusuario de prueba
creado durante el desarrollo — no hace falta correr nada para usarlo:

| Rol           | RUT          | Clave        |
|---------------|--------------|--------------|
| Administrador | 10101010-1   | admin12345   |

⚠️ Es una cuenta de prueba con clave débil. Antes de mostrarle el proyecto a
un cliente real, bórrala (o cámbiale la clave) desde `/admin/` y crea tu
propio superusuario:

```bash
python manage.py createsuperuser
```

Pedirá RUT, correo, nombre y apellidos — **no** pregunta por el rol: se
asigna automáticamente como `administrador`, que es el único rol permitido
para un superusuario.

## Apariencia y accesibilidad

- **Paleta**: "tinta y musgo" — neutros cálidos con dos acentos minerales
  (musgo profundo y arcilla quemada), en vez de la típica paleta
  azul/teal de sitios SaaS. Todo el color vive en variables CSS
  (`static/css/edunova.css`), con un set paralelo para modo oscuro.
- **Modo oscuro**: botón flotante abajo a la derecha, presente en todas
  las páginas (incluido login). Tres opciones: Claro / Oscuro / Auto
  (sigue la preferencia del sistema operativo). Se guarda en
  `localStorage` y se aplica antes de pintar la página para evitar el
  parpadeo del tema por defecto.
- **Accesibilidad**: mismo botón flotante, con tamaño de texto (A / A+ /
  A++), alto contraste, subrayado de enlaces y reducción de animaciones.
  También persiste entre visitas.

Si agregan una plantilla nueva, mientras extienda de `base.html` el botón
de accesibilidad y el modo oscuro funcionan solos — no hay que repetir
nada. Para que cualquier color nuevo respete el modo oscuro, usar las
variables de `edunova.css` (`var(--tinta)`, `var(--rio)`, etc.) en vez de
colores fijos.

## Estructura del proyecto

```
edunova_project/   # settings, urls raíz
usuarios/          # modelo Usuario (custom, login por RUT), login, registro
academico/         # Curso, Estudiante, Asistencia, Observacion,
                    # JustificacionRetiro, Evento (nuevo) + homes de docente/apoderado
comunicacion/       # MensajeComunicacion, envío de comunicados, bandeja,
                    # panel de notificaciones (HTMX)
templates/          # todas las plantillas, organizadas por app
static/css/         # tokens de diseño (paleta, tipografía) que Tailwind CDN no cubre
```

## Roles del sistema

- **docente** y **apoderado**: los únicos que se pueden crear desde el
  registro público del sitio.
- **administrativo**: directores y encargados de asignar cursos,
  evaluaciones, reuniones, etc. No está en el formulario de registro
  público — se crea desde `/admin/` por un `administrador`. Tiene su
  propio home (misma estética que docente/apoderado) con:
  listado y creación rápida de cursos, asignación de docente jefe,
  calendario mensual del colegio completo, y formulario para agendar
  evaluaciones/reuniones/clases en cualquier curso.
- **administrador**: rol para quienes desarrollamos y administramos el
  sitio (no para el colegio) — el acceso técnico vía `/admin/`. Se asigna
  automáticamente al correr `createsuperuser` y no puede elegirse de
  ninguna otra forma (el manager de `Usuario` lo fuerza). Al iniciar sesión
  se le redirige directo a `/admin/`.

## Decisiones tomadas sobre el esquema original

- **Login por RUT**: `Usuario.USERNAME_FIELD = 'rut'`, en vez de un
  username genérico o el email, ya que es lo natural para usuarios
  chilenos. Esto requirió un manager propio (`UsuarioManager`) porque el
  `UserManager` por defecto de Django asume un parámetro literalmente
  llamado `username`.
- **Solo 2 roles en el registro público** (`docente`, `apoderado`): ver
  sección "Roles del sistema" arriba para el detalle de `administrativo` y
  `administrador`.
- **Modelo `Evento` (nuevo, sugerido)**: el esquema original no traía ninguna
  tabla para alimentar un calendario de clases/evaluaciones/reuniones, así
  que se agregó en `academico/models.py`. Es lo que llena el calendario en
  ambos homes.
- **Campos `leido` / `fecha_lectura` en `MensajeComunicacion`** (nuevos): se
  necesitan para que la campana de notificaciones sepa qué mostrar como "no
  leído"; el esquema original no los incluía pero `exige_recibo_lectura` ya
  sugería la necesidad de rastrear esto.
- **`apellido_familiar` en `Estudiante`** (nuevo): permite agrupar hermanos
  bajo una misma tarjeta "Familia X" en el home del apoderado; se calcula
  automáticamente del `nombre_completo` si no se especifica.

## Sugerencias para seguir avanzando

- **Firma digital de comunicados**: el campo `requiere_firma_digital` ya
  existe en el modelo pero no hay flujo de firma implementado — podría
  resolverse con un simple checkbox de "acepto/firmo" + registro de fecha,
  sin necesidad de una librería de firma electrónica avanzada al principio.
- **Recordatorios automáticos**: usando el modelo `Evento`, se puede agregar
  un correo o notificación 24h antes de una evaluación o reunión (Celery o
  un comando periódico simple).
- **Permisos más finos**: hoy cualquier docente puede escribir a cualquier
  apoderado de sus cursos; si más adelante hay más de un docente por curso
  (profesores de asignatura, no solo el jefe), conviene una tabla
  `Curso_Docente` en vez de un solo `docente_jefe`.
- **Exportar reportes**: un botón para descargar la asistencia u
  observaciones del estudiante en PDF sería un plus fácil de vender a un
  colegio o escuela de lenguaje.
- **Comunicados desde Administrativo**: hoy el botón "Nuevo comunicado" se
  oculta para este rol porque el formulario de comunicados solo sabe
  armar las opciones de destinatario/curso para docente y apoderado. Si
  quieren que dirección también pueda enviar comunicados (por ejemplo a
  todo el colegio), hay que extender `ComunicadoForm` para ese caso.
- Cuando definan si el cliente final es el colegio o la escuela de lenguaje,
  conviene revisar quién tendrá cuentas `administrativo` en la práctica
  (¿la dirección?, ¿UTP?) para afinar los permisos de ese panel.
