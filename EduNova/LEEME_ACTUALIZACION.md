# Actualización: reparaciones, secciones y asistencia

## Instalar sobre tu versión actual

Conserva tu base de datos, archivo .env, archivos subidos y entorno virtual. Copia el código de la carpeta EduNova de este ZIP sobre el proyecto, con el servidor detenido.

Con tu entorno virtual activado y la misma configuración de base de datos que ya utilizas, ejecuta:

    python -m pip install -r requirements.txt
    python manage.py migrate
    python manage.py runserver

El ZIP contiene el código y las migraciones; no contiene .env, bases SQLite ni el entorno virtual. Las dependencias de WebSocket ya estaban declaradas en tu versión; deben estar instaladas para iniciar Django.

## Asignar asignaturas a un estudiante en Django Admin

1. Ingresar a /admin/ y abrir Usuarios.
2. La columna Asignaturas del estudiante tiene el enlace Asignar asignaturas / secciones.
3. Se abre la ficha del estudiante. Seleccionar su carrera y una o varias asignaturas/secciones, y guardar.
4. Las secciones seleccionadas deben pertenecer a la carrera elegida. Es obligatorio seleccionar al menos una sección.

También puede hacerse directamente desde Académico > Estudiantes. La sección principal del usuario se sincroniza con la ficha; las matrículas adicionales permanecen en la relación de secciones.

El registro público y la creación/edición de usuarios estudiantes vuelven a exigir una sección principal y la inscriben automáticamente.

## Crear secciones desde el panel Administrativo

El formulario aparece en la Agenda de dirección y en la página Crear sección. Permite seleccionar:

- Carrera: se muestran todas las carreras de la base de datos en la creación de secciones. Los filtros de agenda, observaciones y análisis mantienen su alcance por carrera.
- Asignatura: se carga según la carrera seleccionada.
- Turno: Diurno = true; Vespertino = false.
- Docentes asignados: uno o varios.

Un recuadro de solo lectura muestra el próximo número de tres cifras (000 a 999). El código completo se previsualiza como MAT-000-D o MAT-001-V. El servidor confirma el número al guardar; no confía en un número enviado manualmente desde el navegador.

Los nombres con las mismas tres letras iniciales comparten el correlativo para evitar códigos repetidos. Al agotarse 999, se muestra un error y no se crea otra sección de ese prefijo. Los códigos existentes se convierten al formato con guion antes de D/V manteniendo sus IDs y relaciones. Los códigos históricos que ya superaban 999 se conservan; no se generan nuevos números fuera del rango solicitado.

La creación desde Django Admin también mantiene el formato nuevo y el control del correlativo.

## RegistroAsistencia

En Pasar asistencia y al pulsar Añadir RegistroAsistencia en Django Admin:

1. Elegir curso/asignatura y sección.
2. Ver la tabla con RUT, nombre completo, Presente y Ausente.
3. Marcar una opción por estudiante. No se presume presencia por defecto.
4. Pulsar Guardar asistencia al final.

La fecha y hora se generan en el servidor y se muestran en hora de Santiago como HH-MM--DD/MM/AAAA. Internamente se conservan tipos fecha/hora para permitir filtros y ordenamiento.

Se mantiene una sesión por sección y día y una marca por estudiante. Las correcciones del mismo día actualizan esas marcas; también actualizan el registro histórico asociado a la sección, sin duplicar la lista. Los avisos se crean al registrar o cambiar el estado, no al reenviar un estado idéntico.

Los docentes solo pueden consultar sus secciones. Un director puede acceder a las de su carrera y el superusuario puede acceder desde Django Admin. Una lista de otro docente no se puede sobrescribir por un docente distinto.

## Funciones reparadas

- Panel de observaciones: usa fecha_actualizacion y conserva el filtro de resueltas y positivas.
- Actualización de observaciones: vuelve a la plantilla existente y al formulario con Avisar al estudiante.
- Notificación: la casilla y Guardar envían el mensaje al estudiante vinculado, visible en su bandeja y campana. Se informa si falta una cuenta.
- Permisos: estudiantes y docentes ajenos no pueden consultar ni modificar observaciones; los directores trabajan con las de su carrera. Los registros que mezclan estudiantes de carreras distintas no se pueden modificar desde una dirección parcial.
- Creación de observaciones: las secciones y los alumnos se validan según el docente y las matrículas.
- Registro público: se restauran el campo de sección y su validación, corrigiendo la plantilla que hacía referencia a un campo ausente.
- Reportes CSV: se restauran las rutas y el acceso desde la agenda administrativa.
- Carga de alumnos: se corrige la respuesta JSON y se añaden RUT, estado previo y hora del registro.
- Asistencia histórica: la migración 0015 incorpora al análisis los registros antiguos con una sección identificable. Respeta las marcas modernas existentes y la última corrección histórica. No genera avisos retrospectivos.

Los registros históricos sin una sección identificable se conservan en su tabla original; no se asignan a una materia arbitraria. Pueden revisarse en Django Admin. Al modelar varias secciones, no es posible deducir retrospectivamente a cuál correspondía una asistencia sin esa información.

## Tablas

Se auditó su uso directo e indirecto. No se encontraron tablas sin función, por lo que no se incorporaron operaciones DeleteModel/DropTable. AUDITORIA_TABLAS.md detalla para qué se conserva cada grupo. Las tablas históricas no se consideran sobrantes: contienen información, alimentan la migración y siguen disponibles para consulta.

Se conserva el rol histórico Apoderado para mantener válidos los datos y las pantallas anteriores; no se agrega al registro público.

## Verificación

56 pruebas aprobadas en SQLite, incluidos los flujos de Django Admin, inscripción múltiple, registro, permisos, creación de secciones, límite 999, RUT, guardado/corrección de asistencia, importación histórica y entrega privada de WebSocket.
Django check sin problemas y makemigrations --check sin cambios pendientes.

Se ejecutaron las migraciones sobre una copia de la base SQLite incluida en el ZIP recibido: se conservaron sus 3 cursos, 3 estudiantes y 8 registros históricos de RegistroAsistencia, se generaron 13 marcas para análisis incluyendo el otro modelo histórico y no se encontraron errores de claves foráneas.

No se modificó la base original ni se probó contra un servidor PostgreSQL o Redis externo.

## Corrección del selector y el número automático

El selector de creación de secciones ofrece todas las carreras registradas, incluidas las que no coinciden con la carrera dirigida del usuario. Las asignaturas se filtran según la carrera seleccionada.

La primera asignatura de la carrera se selecciona automáticamente y el número real se muestra al abrir el formulario. Al cambiar carrera o asignatura se actualiza; al cambiar turno se actualiza D/V. Tras crear la sección, se calcula el siguiente correlativo. El servidor vuelve a confirmar el número al guardar para evitar duplicados.

El script se entrega en static/js/secciones-form.js. Si sirves los archivos estáticos con collectstatic, actualízalos también:

    python manage.py collectstatic --noinput

Esta corrección no agrega migraciones. Mantén las migraciones de la entrega anterior aplicadas. Reinicia el servidor y recarga la página con Ctrl+F5.

Se verificaron 56 pruebas de Django. La comprobación visual del navegador no pudo realizarse porque su control de permisos rechazó el acceso al servidor local de pruebas.
