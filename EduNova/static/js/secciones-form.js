(() => {
  function iniciar() {
    document.querySelectorAll('form[data-opciones-url]').forEach(form => {
      if (form.dataset.seccionInicializada) return;
      form.dataset.seccionInicializada = 'true';
      const carrera = form.querySelector('[name="carrera"]');
      const asignatura = form.querySelector('[name="asignatura_catalogo"]');
      const turno = form.querySelector('[name="turno"]');
      const numero = form.querySelector('[name="numero_previo"]');
      const codigo = form.querySelector('#codigo-seccion');
      const error = form.querySelector('#error-seccion');
      const guardar = form.querySelector('button[type="submit"]');
      if (!carrera || !asignatura || !turno || !numero) return;
      let version = 0;
      let prefijo = '';
      function mostrar() {
        codigo.textContent = prefijo && numero.value
          ? `${prefijo}-${numero.value}-${turno.value === 'true' ? 'D' : 'V'}`
          : 'Selecciona una carrera y una asignatura.';
      }
      async function consultar(parametros) {
        const response = await fetch(form.dataset.opcionesUrl + '?' + parametros.toString(), {credentials: 'same-origin'});
        if (!response.ok) {
          let mensaje = 'No se pudo obtener el número de sección. Inténtalo nuevamente.';
          try { mensaje = (await response.json()).error || mensaje; } catch (_) {}
          throw new Error(mensaje);
        }
        return response.json();
      }
      async function actualizar(cambiarCarrera) {
        const actual = ++version;
        guardar.disabled = true;
        error.textContent = '';
        numero.value = '';
        prefijo = '';
        mostrar();
        if (!carrera.value) {
          asignatura.replaceChildren(new Option('Seleccionar asignatura', ''));
          return;
        }
        try {
          const parametros = new URLSearchParams({carrera: carrera.value});
          let datos;
          if (cambiarCarrera) {
            asignatura.disabled = true;
            datos = await consultar(parametros);
            if (actual !== version) return;
            asignatura.replaceChildren(new Option('Seleccionar asignatura', ''));
            datos.asignaturas.forEach(a => asignatura.add(new Option(a.nombre, a.id)));
            if (datos.asignaturas.length) asignatura.value = String(datos.asignaturas[0].id);
            asignatura.disabled = false;
          }
          if (!asignatura.value) {
            codigo.textContent = 'Esta carrera no tiene una asignatura seleccionada.';
            return;
          }
          parametros.set('asignatura', asignatura.value);
          datos = await consultar(parametros);
          if (actual !== version) return;
          numero.value = datos.numero;
          prefijo = datos.prefijo;
          mostrar();
          guardar.disabled = false;
        } catch (e) {
          if (actual === version) {
            asignatura.disabled = false;
            error.textContent = e.message;
          }
        }
      }
      carrera.addEventListener('change', () => actualizar(true));
      asignatura.addEventListener('change', () => actualizar(false));
      turno.addEventListener('change', mostrar);
      window.addEventListener('pageshow', event => { if (event.persisted) actualizar(false); });
      actualizar(!asignatura.value);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
