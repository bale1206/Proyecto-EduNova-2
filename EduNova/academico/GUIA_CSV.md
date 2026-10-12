# Exportación e importación CSV de EduNova

## Análisis del proyecto

EduNova usa Django 6.1.1 y SQLite, con las aplicaciones `usuarios`,
`academico` y `comunicacion`. El panel administrativo existente permite
gestionar cursos y eventos. Antes de este cambio no había exportación,
importación ni una identidad separada para dirección.

Se utiliza el rol existente `administrativo` para representar a dirección,
seleccionar tablas y operar los CSV. No se añade un rol separado de director.
El administrativo conserva su panel y obtiene accesos a configuración y CSV.
El administrador del sistema crea o modifica las cuentas desde `/admin/`.

## Puesta en marcha

1. Descomprime esta versión en una carpeta independiente o incorpora los
   archivos modificados a tu proyecto. Conserva una copia de tu base de datos.
2. Usa un entorno compatible con las dependencias de `requirements.txt`.
   El ZIP no incluye el entorno virtual ni el historial Git.
3. Ejecuta `python manage.py migrate` para crear la tabla de permisos.
   La base de datos incluida conserva
   los datos originales; las migraciones nuevas todavía deben aplicarse.
4. Usa una cuenta existente con rol **Administrativo**, o crea una desde
   `/admin/`. No necesita permisos de superusuario ni `is_staff`.
5. Inicia sesión como administrativo. En **Permisos CSV** (`/direccion/csv/`), marca las tablas
   y las operaciones permitidas y guarda. Todas empiezan deshabilitadas.
6. Inicia sesión como administrativo. En su panel abre **Reportes e
   importación CSV**, o visita `/administrativo/csv/`.

La selección es común a todos los administrativos, con exportación e
importación autorizadas de forma independiente. Todas las cuentas con
este rol pueden cambiar esa selección, ya que el director utiliza el
mismo rol. No existe separación de permisos entre dirección y el resto
del personal administrativo. El rol `administrador` sigue reservado al
panel técnico `/admin/` y no configura ni opera este módulo.

## Tablas disponibles

Se incluyen las tablas de negocio de `academico` y `comunicacion` y la
tabla intermedia de estudiantes de una observación de comportamiento.
No se incluyen cuentas, contraseñas, sesiones, permisos del sistema ni la
propia tabla de configuración CSV.

El director ve el nombre físico, las columnas en orden, sus tipos,
si admiten NULL y las tablas relacionadas. Cada tabla tiene su propio CSV;
los datos relacionados no se fusionan en el reporte.

## Formato

- Exportación: UTF-8 con BOM, separador punto y coma, encabezado con todas las
  columnas físicas en su orden real y todos los registros ordenados por ID.
  Las claves foráneas se exportan como `curso_id`, `apoderado_id`, etc.
  La primera línea es `sep=;`: Excel la interpreta como indicación de
  separador para abrir cada campo en su columna, independientemente de su
  configuración regional. La segunda línea contiene los nombres de columnas.
- Importación: UTF-8 con o sin BOM; separador coma o punto y coma.
  Deben coincidir todas las columnas y su orden. No se admiten columnas
  faltantes, adicionales, repetidas o renombradas.
  Se admite la línea opcional `sep=;` o `sep=,` antes del encabezado,
  de modo que se pueden importar los reportes y plantillas directamente.
- Las comillas, comas y saltos de línea siguen las reglas habituales de CSV.
  Texto vacío y NULL son distintos: NULL se escribe como `\N`. Para
  representar una barra invertida literal se utilizan dos barras invertidas.
- Fechas: `AAAA-MM-DD`; horas: `HH:MM:SS`; fecha y hora: ISO 8601,
  por ejemplo `2026-10-12T09:00:00-03:00`.
- Decimales con punto; booleanos `true`/`false` o `1`/`0`.
- Un ID vacío genera un ID nuevo. Un ID explícito debe ser nuevo.
  Los IDs relacionados deben existir y respetar el rol exigido por el modelo.
- Los valores con opciones usan el código de la base de datos, por ejemplo
  `presente`, `positiva` o `POSITIVA`, según la tabla y el campo.
- Para campos de archivo, el CSV contiene la ruta registrada; los archivos
  adjuntos no se transfieren con el CSV.

Ejemplo para `academico_curso` (si el usuario 10 es docente):

```csv
sep=;
id;grado_curso;docente_jefe_id
;1° Básico A;10
;1° Básico B;\N
```

El administrativo puede descargar una plantilla sin registros cuando
tiene permiso de importación, incluso si no tiene permiso de exportación.
El CSV representa columnas y valores; no es un respaldo de SQL con
definiciones CREATE TABLE, índices o archivos adjuntos.

## Comportamiento de importación

La importación añade registros; no actualiza, sobrescribe ni borra los
existentes. Importar un reporte en su misma tabla sin cambiar los IDs
fallará por duplicados. Para restaurarlo, la tabla destino debe admitir
esos IDs; para añadir registros nuevos, deja vacía la columna `id`.

Se validan tipos, longitudes, valores permitidos, referencias, claves
únicas y restricciones del modelo. Se conserva lo indicado en el archivo,
incluidas las fechas automáticas y los campos calculados en `save()`:
la importación no autocompleta apellido familiar, folio ni estado.
El archivo debe traer esos datos. Esto permite conservar los valores de
un reporte exportado.

Máximo por carga: 5 MB y 10.000 registros. Una fila inválida cancela
toda la importación, incluso si las anteriores eran válidas. El panel
indica el registro afectado y el motivo. Importa primero las tablas
referenciadas; la tabla intermedia de observaciones se carga después de
las observaciones y los estudiantes.

Los permisos se comprueban en el servidor para cada operación. Durante
la importación se vuelve a comprobar la autorización dentro de la
transacción. Los formularios de escritura están protegidos por CSRF.

Los reportes conservan el contenido de los textos. Al abrirlos en una
hoja de cálculo, importa las columnas de texto como texto para mantener
RUT, ceros iniciales y textos que comienzan con signos de fórmula.

## Validación realizada

`python manage.py test academico usuarios comunicacion`: 15 pruebas
aprobadas, incluyendo la prueba preexistente de asistencia. Se verificaron:

- Acceso exclusivo del rol administrativo y rechazo de tablas protegidas.
- Configuración compartida entre administrativos, exportación, plantilla y formulario de carga.
- Conservación de tildes, comillas, saltos de línea y barras invertidas.
- Encabezados incorrectos, archivos mal formados, límites y codificación.
- Duplicados, referencias inválidas y reversión completa ante errores.
- Conservación de fechas automáticas, booleanos y NULL.
- Importación de la tabla intermedia de relaciones muchos a muchos.
- Separador explícito de Excel y una columna independiente para cada dato
  de asistencia, incluidos ID, fecha, porcentaje y referencias.

`python manage.py check` no detectó problemas. `makemigrations --check
--dry-run` confirmó que los cambios de modelos tienen sus migraciones.
Las pruebas usan una base temporal y no alteran los datos originales.

## Archivos principales del cambio

- `academico/csv_services.py`: catálogo, esquema, exportación y carga.
- `academico/csv_views.py`: permisos, paneles y operaciones HTTP.
- `academico/models.py` y migración `0005`: configuración de tablas.
- Se conservan los roles y la redirección de inicio de sesión originales.
- `academico/urls.py`: rutas del módulo.
- Plantillas CSV, navegación y acceso desde el panel administrativo.
- `academico/test_csv.py`: pruebas del módulo.

No se cambió la configuración de despliegue ni se publicó el proyecto.
