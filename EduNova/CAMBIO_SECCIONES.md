# Secciones y matrículas múltiples (transición compatible)

- Django Admin presenta «Secciones de asignaturas», con un catálogo de asignaturas y **varios docentes por sección**.
- En el admin de Estudiantes se exige **una o más secciones** y se oculta el campo escolar `curso`.
- El portal docente y la toma de asistencia muestran todas las secciones asignadas.
- Migración 0013 crea la relación M:N entre docentes y secciones y traslada el docente existente de cada sección.
- Cada estudiante ya tenía una relación M:N `secciones`; se conserva y se utiliza.
- `Curso`, `curso`, y `docente_jefe` continúan en la base de datos para compatibilidad con modelos históricos, observaciones, comunicaciones, eventos y CSV. No eliminar estas columnas sin una migración integral de referencias.
- La obligatoriedad de sección se valida **en Django Admin**; no se aplica todavía a nivel SQL, ya que se requiere crear usuarios y perfiles antes de realizar matrículas en una segunda operación.
- Para los docentes, la asignación de una o más secciones se realiza mediante el admin de Secciones, no el formulario de Usuarios. El alta de usuario no fuerza matrícula previa.
- Recomendación: migrar por separado los enlaces de `Curso` a `Seccion` en todos los módulos y agregar verificaciones de integridad antes de retirar las columnas legadas.
