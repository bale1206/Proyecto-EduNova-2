# Corrección del panel de asistencia

## Uso

1. Con tu entorno de Python habitual activado, entra a la carpeta que contiene `manage.py`.
2. Antes de actualizar una instalación existente, conserva una copia de tu base de datos y de tu archivo `.env`.
3. Si instalas el proyecto desde cero: `python -m venv venv`, activa el entorno e instala `pip install -r requirements.txt`.
4. Ejecuta `python manage.py migrate` para aplicar las migraciones pendientes del proyecto original. Esta corrección no agrega migraciones nuevas.
5. Inicia con `python manage.py runserver`.
6. Entra como administrativo y abre **Análisis de asistencia**. Selecciona carrera, asignatura y sección, y pulsa **Aplicar filtros**.
7. Para las secciones antiguas que no tienen asignatura de catálogo, selecciona **Secciones sin catálogo (histórico)** en el filtro Carrera. Esta opción consulta todas las carreras; no atribuye una carrera a esas secciones.

La base SQLite incluida en el ZIP original tiene tres secciones sin catálogo y tres estudiantes sin carrera asignada. Por eso esas secciones no aparecían entre las materias de una carrera. Para integrarlas a esos filtros, vincula cada sección a la asignatura correcta y asigna la carrera de sus estudiantes desde la administración.

El `.env` y las bases de datos se conservan como en el archivo recibido. Se usa PostgreSQL según la configuración original; para utilizar expresamente la base SQLite local configura `DB_ENGINE=sqlite`. El entorno virtual no se incluye en esta entrega: debe crearse en el equipo donde se ejecutará el proyecto.

## Cálculo

**Porcentaje = presencias / (presencias + ausencias) × 100**, redondeado a un decimal.

- Una marca por estudiante, sección y día. Al corregir la lista, se usa el valor vigente.
- La marca de sesión (`MarcaAsistencia`) tiene prioridad sobre `RegistroAsistencia`, y este sobre el modelo escolar `Asistencia`. Las copias no se suman otra vez.
- Los registros históricos sin sección solo se atribuyen cuando el estudiante tiene una única sección identificable. Los registros ambiguos quedan fuera del cálculo.
- Los registros de secciones eliminadas con marcas conservadas no se reasignan a otra sección.
- En el historial escolar, presente y atraso cuentan como presencia; ausente y justificado como ausencia. El campo de porcentaje manual no se usa para calcular el panel.
- En el filtro de una carrera se incluyen los registros de sus estudiantes y los de estudiantes sin carrera asignada en las secciones seleccionadas; el panel informa cuántos registros son de estudiantes sin carrera. Se excluye a estudiantes con otra carrera conocida.
- El total se obtiene de todos los registros seleccionados; no promedia los porcentajes de las secciones.
- Sin registros se muestra “Sin registros” o un guion, y no un 0 % ficticio.
- El gráfico recibe el decimal con punto para que el estilo CSS funcione con la configuración regional española.

## Archivos modificados o añadidos

- `academico/analitica.py`: consolidación y cálculo de asistencia.
- `academico/views.py`: integración del resumen y selección explícita del historial sin catálogo.
- `templates/academico/analitica_carrera.html`: gráfico, explicación del cálculo y opción de historial.
- `academico/test_analitica.py`: nueve pruebas de regresión.

## Verificación

Se ejecutaron las 70 pruebas del proyecto con Django 6.1.1 y SQLite: todas pasaron. También se aplicaron las migraciones originales sobre una copia de la base SQLite incluida, sin modificar el archivo entregado. No se conectó ni se modificó la base PostgreSQL configurada en el `.env`.

Comando de pruebas: `python manage.py test --noinput`.
