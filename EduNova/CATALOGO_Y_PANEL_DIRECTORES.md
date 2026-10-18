# Dirección por carrera y catálogo académico

Los 13 programas se toman de la sede Antonio Varas de Duoc UC. Se precargan tres asignaturas por programa al ejecutar `python manage.py migrate`. La carga es idempotente por código y carrera; no crea nuevas secciones ni elimina registros existentes.

## Ingeniería en Informática
- FPY1101: Fundamentos de Programación
- DSY1101: Introducción a Cloud Computing
- MAT1111: Nivelación Matemática
Fuente: https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1446115-2024-Ingenieroa-en-Informa%CC%81tica.pdf

## Ingeniería en Infraestructura Tecnológica
- INY1102: Fundamentos Cloud I
- BIY1101: Bases de Innovación
- ADY1101: Sistemas Operativos I
Fuente: https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1446815-2024-Ingenieroa-en-Infraestructura-Tecnolo%CC%81gica-PRESENCIAL.pdf

## Ingeniería en Redes y Telecomunicaciones
- AYV1101: Introducción a las Telecomunicaciones
- AYV1182: Soporte Computacional IT Essentials
- AYV1108: Conectividad de Redes
Fuente: https://www.duoc.cl/wp-content/uploads/2025/09/Malla-Curricular-1445101-2025-Ingenieroa-en-Redes-y-Telecomunicaciones.pdf

## Administración en Turismo y Hospitalidad
- NHT1101: Ecosistema de la Industria Turística
- NHT1102: Mindset Turismo y Hospitalidad
- MCT1201: Marketing y Comercialización para Turismo y Hotelería
Fuente: https://www.duoc.cl/wp-content/uploads/2025/10/ATH_mencio%CC%81n-Administracio%CC%81n-Hotelera_diploma-Hoteleri%CC%81a.pdf

## Ingeniería en Marketing Digital
- MKA1101: Introducción al Marketing
- VNA1101: Fundamentos de Ventas
- ANA1201: Fundamentos de Economía
Fuente: https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1116216-2023-Ingeniero-en-Marketing-Digital-PRESENCIAL.pdf

## Auditoría
- TRA1100: Legislación Tributaria
- CCA1101: Contabilidad I
- FNA1101: Administración y Economía
Fuente: https://www.duoc.cl/wp-content/uploads/2026/01/Malla-Curricular-1117101-2026-Contadora-Auditora-Auditori%CC%81a-y-ana%CC%81lisis-de-negocios-FOL.pdf

## Ingeniería en Gestión Logística
- LOG-INTRO: Introducción a la Logística
- LOG-TRANS: Operaciones de Transporte
- LOG-ALMAC: Operaciones de Almacenamiento
Fuente: https://www.duoc.cl/wp-content/uploads/2024/10/6-ING-GESTION-LOGISTICA.pdf

## Ingeniería en Comercio Exterior
- ABA1101: Introducción al Comercio Exterior
- ABA1102: Introducción a la Logística
- GAA1101: Herramientas Tecnológicas I
Fuente: https://malla.duoc.cl/malla/administracion-negocios/011-ing-comercio-exterior.html

## Ingeniería en Administración Mención Gestión de Personas
- LCA0121: Fundamentos de Contabilidad
- GEA1101: Normas y Procedimientos
- GEA1108: Fundamentos de Economía
Fuente: https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1116415-2024-Ingenieroa-en-Administracio%CC%81n-mencio%CC%81n-Gestio%CC%81n-de-Personas-PRESENCIAL.pdf

## Ingeniería en Administración Mención Innovación y Emprendimiento
- LCA8121: Fundamentos de Contabilidad
- GEA1811: Normas y Procedimientos
- GEA1808: Fundamentos de Economía
Fuente: https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1116711-2024-Ingenieroa-en-Administracio%CC%81n-mencio%CC%81n-Innovacio%CC%81n-y-Emprendimiento-PRESENCIAL.pdf

## Ingeniería en Administración Mención Finanzas
- LCA0121: Fundamentos de Contabilidad
- GEA1101: Normas y Procedimientos
- GEA1108: Fundamentos de Economía
Fuente: https://malla.duoc.cl/malla/administracion-negocios/007-ing-administracion-m-finanzas.html

## Técnico en Administración
- LCA0121: Fundamentos de Contabilidad
- GEA1101: Normas y Procedimientos
- GEA1108: Fundamentos de Economía
Fuente: https://www.duoc.cl/wp-content/uploads/2025/09/Malla-Curricular-1111212-2024-Tecnico-en-Administracion.pdf

## Gastronomía Internacional
- GAS-COC: Cocina Básica
- GAS-PAN: Panadería
- GAS-HIG: Higiene y Prevención de Riesgos
Fuente: https://www.duoc.cl/wp-content/uploads/2025/09/Malla-Curricular-667017-2024-Gastronomia-Internacional.pdf

Los códigos de demostración `LOG-*` y `GAS-*` no son códigos oficiales; se emplean porque la malla referenciada permite comprobar los nombres pero no sus códigos.

**Administración:** En `/admin/`, editar usuario director (rol administrativo) y seleccionar `Carrera dirigida`. Una cuenta tiene un solo campo de carrera. Crear o editar asignaturas en `/admin/academico/asignatura/`; crear secciones en `/admin/academico/curso/` eligiendo una asignatura del catálogo. Los otros roles no tienen formularios para crear asignaturas.

**Analítica:** el panel nuevo `/administrativo/analitica/` filtra por la carrera del director y luego por asignatura. Estudiantes matriculados contados solo si pertenecen a esa carrera. No inventa calificaciones ni tasa de aprobación. Una asignatura precargada no genera automáticamente una sección: su cantidad inicial puede ser cero.

**Compatibilidad:** se conserva la tabla `Curso` y su nombre de asignatura legado para no perder los datos históricos. Las secciones previas solo se asocian por coincidencia exacta del nombre; otras requieren vincularse en Django Admin. Los reportes CSV no están accesibles desde el portal de dirección.

**Seguridad:** antes de migrar Supabase, respaldar la base. Revisar en Django Admin cada cuenta directora y asignar su carrera. El acceso del director sin carrera mostrará una pantalla de espera, no datos de todas las carreras.

**Nota de alcance:** La analítica utiliza cantidades reales disponibles (inscritos, secciones y evaluaciones), no datos simulados. Si no hay secciones asignadas al catálogo, mostrará cero. El módulo heredado CSV se mantiene en código/migraciones por compatibilidad, pero no tiene acceso desde dirección. Eliminar físicamente todas las tablas antiguas requeriría una migración destructiva que no se realiza aquí.
