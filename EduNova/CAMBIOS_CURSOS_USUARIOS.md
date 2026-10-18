# Cursos y usuarios: actualización

Esta versión incluye también los cambios anteriores de observaciones y notificaciones.

## Curso

- Asignatura: nombre de la materia (mínimo tres letras).
- Turno: selector Diurno o Vespertino, almacenado como booleano true o false respectivamente.
- Sección: se genera automáticamente y reemplaza el grado en los listados. No se escribe manualmente en los formularios.
- El código usa las primeras tres letras en mayúsculas, sin tildes, un guion, un correlativo desde 000 y D o V.
- Ejemplo: Matemática diurna → MAT-000D; Materiales vespertina → MAT-001V; Matemática vespertina → MAT-002V.
- Los nombres que comparten las primeras tres letras comparten el correlativo, incluso entre turnos. Programación empieza su propio correlativo PRO-000D.
- El correlativo admite más de tres dígitos al llegar a 1000. No se permiten duplicados de prefijo y número en la base de datos.
- Al cambiar el prefijo de asignatura o el turno, se genera una sección nueva; el ID y las relaciones de asistencia, eventos y observaciones se conservan.
- Se actualizan tanto el formulario del panel Administrativo como la administración /admin/ y los ejemplos de importación CSV.

## Usuario estudiante

- El registro y la creación/edición de usuarios en /admin/ exigen seleccionar un curso cuando el rol es Estudiante.
- En el registro público, el selector se muestra al elegir Estudiante.
- El curso se presenta con sección, asignatura y turno para distinguir las opciones.
- Se crea o vincula la ficha del estudiante, conservando su ID si ya existía sin cuenta vinculada. Esa ficha y el curso del usuario permanecen sincronizados al editar cualquiera de los dos.
- El apoderado pasa a ser opcional para poder registrar la cuenta del estudiante sin exigir una cuenta de apoderado.
- El calendario, la asistencia y las notificaciones continúan usando la ficha vinculada.

## Actualizar tu instalación

1. Conserva tu base de datos actual, archivo .env y entorno virtual.
2. Reemplaza los archivos de código y plantillas con los de la carpeta EduNova de este ZIP.
3. Con tu entorno virtual activado y la configuración habitual de base de datos, ejecuta:

   python manage.py migrate
   python manage.py runserver

El ZIP no contiene db.sqlite3 ni el entorno virtual, para que conserves los de tu instalación. No requiere dependencias nuevas respecto a requirements.txt.
Para una instalación completamente nueva:

   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt

La configuración original usa PostgreSQL por defecto. Si ya trabajas con SQLite, conserva DB_ENGINE=sqlite. En PowerShell puede establecerse así antes de migrate y runserver:

   $env:DB_ENGINE = 'sqlite'

## Datos existentes

Las migraciones conservan los IDs y las relaciones. Como la base anterior no tenía asignatura ni turno, se conserva el nombre anterior como referencia de asignatura y se usa Diurno inicialmente. Si el nombre tenía menos de tres letras, se antepone Curso para poder generar el prefijo. Revisa esos cursos en /admin/academico/curso/ y completa la asignatura y el turno reales.

Los usuarios estudiantes con una ficha y un curso ya vinculados reciben ese mismo curso automáticamente. Si en tu base actual hay estudiantes sin curso, asígnalo al editarlos en /admin/usuarios/usuario/; no se elige un curso arbitrario.

## Verificación

- 41 pruebas automatizadas aprobadas con SQLite.
- Incluyen registro, creación/edición en /admin/, permisos del panel Administrativo, turnos booleanos, correlativos por prefijo, restricciones únicas, sincronización de fichas, CSV y avisos de observaciones.
- Se probó la migración desde la estructura anterior, preservando IDs y vínculos de usuarios, cursos y estudiantes.
- Además se aplicaron todas las migraciones a una copia de db.sqlite3 del proyecto original; sus tres cursos y tres estudiantes se conservaron.
- Django check sin errores y makemigrations --check sin cambios pendientes.
- No se realizó una prueba con un servidor PostgreSQL externo.
