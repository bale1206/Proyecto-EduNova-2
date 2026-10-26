# EduNova: registro de cuentas y dos planillas universitarias

## Registro
La creación pública de cuentas pide solo identidad, contacto, contraseña y rol (docente o estudiante). No permite seleccionar carrera, sección ni asignatura. Las cuentas de estudiante se vinculan posteriormente a su ficha académica; cada estudiante utiliza **una sola cuenta**.

## Planillas disponibles
Solo dirección de carrera puede acceder a **Planillas académicas** (`/csv/` según enrutamiento principal). La importación **actualiza por RUT cuentas y fichas existentes**; nunca crea usuarios ni nuevas asignaturas o secciones. Los archivos son CSV UTF-8. Se validan completos antes de guardar, con transacción única.

- **Docentes:** `rut,codigos_asignaturas`. Códigos separados por `;` y debidamente entrecomillados si corresponde: `"MAT101;PROG101"`. No aparece la carrera en el archivo. Los códigos se comprueban contra el catálogo de asignaturas de la carrera que dirige el usuario autenticado, pero el docente puede impartir asignaturas de distintas carreras. No se asignan automáticamente secciones ni se borran sus asignaturas de otras carreras. Las asociaciones existentes se precargan desde secciones al migrar.
- **Estudiantes:** `rut,carrera,anio_carrera,estado_avance`. Años 1, 2, 3 o 4. Estado `al_dia` o `con_retraso`. El campo **carrera** debe coincidir con la carrera del director autenticado y del estudiante registrado; no permite cambiar al estudiante a otra carrera ajena. Estado y año son **datos manuales estáticos**, sin conexión con las notas, reprobaciones ni la aplicación institucional de progreso académico de Duoc UC.

## Instalación
Conserva tu `.env` local (no se incluye en el ZIP), respalda Supabase y ejecuta en la raíz de EduNova:

```powershell
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py runserver
```

Migraciones nuevas:
- `usuarios/0007_asignaturas_docentes_csv.py`: asociación muchos a muchos entre docentes y asignaturas (incluye copia desde secciones existentes).
- `academico/0017_avance_estudiante_csv.py`: año y situación académica declarada de los estudiantes.

Los modelos y tablas históricos de Django no se destruyen por seguridad, pero se retiraron las rutas, formularios y servicios para importar/exportar cualquier otra tabla. El registro ya no exige seleccionar un curso.

## Límites
Los archivos solo actualizan personas ya creadas, lo cual evita la generación insegura de contraseñas por CSV. Para nuevas personas primero registra las cuentas/fichas por el mecanismo administrativo existente. El estado académico es declarativo y no puede calcularse automáticamente desde las notas actuales.

Se verificó compilación Python e integridad del ZIP. **Las migraciones y pruebas funcionales no se ejecutaron contra tu Supabase**, por lo que deben comprobarse antes de aplicar en producción.
