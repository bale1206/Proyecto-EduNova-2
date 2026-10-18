# Nuevas funcionalidades: asistencia y analítica

## Cambios

- **Dirección de carrera, vista general**: agenda de reuniones y otros eventos, sin métricas en esa vista. La analítica se consulta en su propia ruta.
- **Analítica**: muestra porcentaje de marcas de asistencia presentes, restringido a estudiantes de la carrera del director. Filtros por asignatura y sección. Las secciones compartidas no exponen estudiantes de otras carreras.
- **Docente**: registro de presentes/ausentes por sección en el día actual. Si vuelve a guardar ese día, actualiza las marcas, no genera duplicados. Solo puede utilizar sus propias secciones.
- **Estudiante**: guarda avisos positivos o de ausencia por cada marca nueva o corregida, y transmite en tiempo real por WebSocket cuando su sesión está abierta.

## Instalación

1. Conservar `.env` fuera del ZIP y respaldar Supabase antes de migrar.
2. `pip install -r requirements.txt`
3. `python manage.py migrate` (crea SesionClase, MarcaAsistencia, AvisoAsistencia)
4. `python manage.py check`
5. `python manage.py runserver` (Daphne/Channels atiende `/ws/avisos/estudiante/`)
6. Probar con un estudiante que tenga su cuenta `Estudiante.usuario` enlazada, una matrícula `Estudiante.secciones` y un docente asignado como `Curso.docente_jefe`.

## Importantísimo

- Los registros antiguos de `RegistroAsistencia` y `Asistencia` se conservan y **no se migran automáticamente a la analítica**, porque no guardan una sección/fecha comparable de manera inequívoca. La analítica comienza con las sesiones nuevas, evitando cifras históricas erróneas.
- Los porcentajes se calculan sobre registros efectivamente marcados: presencias / (presencias + ausencias), no sobre el universo esperado de clases. Si no hay datos se presenta “Sin registros”.
- Solo se permite registrar o corregir asistencia para la fecha de hoy desde el formulario.
- El sistema crea un aviso nuevo cuando cambia la marca. Guardar sin cambiarla no genera avisos adicionales. Los avisos persistidos se pueden leer en el portal estudiante incluso cuando la conexión WebSocket estaba cerrada.
- En desarrollo una sola instancia usa InMemoryChannelLayer. En producción, para varias instancias, configurar `REDIS_URL` y HTTPS/WSS con un servidor ASGI. Supabase PostgreSQL no reemplaza el intermediario Redis para WebSocket.
- **Pruebas funcionales pendientes:** este entorno no cuenta con Django instalado y no se ha conectado a Supabase. Ejecutar pruebas de autorización por sección, de notificación y de cálculo antes de desplegar.
- Nunca subir `.env` al repositorio.
