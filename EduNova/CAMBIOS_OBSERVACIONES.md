# Cambios solicitados: observaciones

- Se retira Positiva de las opciones de creación y actualización de observaciones.
- Las positivas anteriores se ocultan del panel y del listado de observaciones recientes; se conservan en la base de datos para no eliminar historial.
- Negativa cambia a Sanción en ambos modelos de observaciones. La migración 0007 convierte las negativas existentes conservando sus demás datos.
- La casilla ahora dice Avisar al estudiante. Al marcarla y guardar los cambios, envía un mensaje interno a la cuenta vinculada mediante Estudiante.usuario, siempre que tenga rol estudiante.
- El aviso aparece en la bandeja y la campana de notificaciones. No se envía al apoderado.
- Se informa cuántos estudiantes fueron notificados y cuáles carecen de una cuenta con el rol requerido. Es necesario vincular esas cuentas en la administración.
- La actualización y los avisos se guardan juntos: si falla el envío, se revierte la operación.

## Aplicar en tu instalación existente

1. Respaldar la base de datos y reemplazar los archivos del proyecto por esta versión. Conservar la configuración .env y el entorno virtual propios.
2. Con el entorno virtual activado, ejecutar:

   python manage.py migrate

3. Iniciar normalmente:

   python manage.py runserver

Para una instalación nueva, crear el entorno virtual e instalar primero las dependencias de requirements.txt:

   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt

La configuración original usa PostgreSQL de manera predeterminada. Para usar la copia SQLite incluida, en PowerShell ejecutar antes de migrate y runserver:

   $env:DB_ENGINE = 'sqlite'

El archivo db.sqlite3 incluido se conserva igual al original; su migración se aplica con el comando indicado. El ZIP no incluye el entorno virtual, que se debe crear o conservar en cada equipo.

## Verificación realizada

25 pruebas automatizadas aprobadas usando SQLite, incluidas 8 nuevas para opciones, conversión de datos, destinatarios, bandeja, campana, control de lectura, casilla desmarcada, cuentas ausentes y reversión ante errores.
Django check sin problemas y makemigrations --check sin cambios pendientes.
No se probó con una conexión PostgreSQL externa.
