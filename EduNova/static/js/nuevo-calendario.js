// Un solo menú y una ventana por calendario. Sin recargas automáticas ni peticiones idle.
(function () {
  'use strict';
  function iniciar(root) {
    const menu = root.querySelector('.edunova-nuevo-menu');
    const dialogo = root.querySelector('.edunova-nuevo-modal');
    const tipo = root.querySelector('[data-tipo-input]');
    const titulo = root.querySelector('[data-titulo-modal]');
    if (!dialogo || !menu || !tipo || !titulo) return;
    const nombres = { tarea: 'tarea', reunion: 'reunión', evaluacion: 'evaluación', evento: 'evento', otro: 'evento' };
    root.querySelectorAll('[data-crear-tipo]').forEach(boton => {
      boton.addEventListener('click', () => {
        const valor = boton.dataset.crearTipo;
        if (!Object.prototype.hasOwnProperty.call(nombres, valor)) return;
        tipo.value = valor;
        titulo.textContent = (valor === 'otro' || valor === 'evento' ? 'Nuevo ' : 'Nueva ') + nombres[valor];
        menu.open = false;
        if (typeof dialogo.showModal === 'function') dialogo.showModal();
      });
    });
    root.querySelectorAll('[data-cerrar-nuevo]').forEach(boton => {
      boton.addEventListener('click', () => dialogo.close());
    });
    dialogo.addEventListener('click', evento => {
      if (evento.target === dialogo) dialogo.close();
    });
    const alcance = root.querySelector('[data-alcance]');
    const grupo = root.querySelector('[data-grupo-seccion]');
    if (alcance && grupo) {
      const campo = grupo.querySelector('select');
      const actualizar = () => {
        const porSeccion = alcance.value === 'seccion';
        grupo.hidden = !porSeccion;
        if (campo) campo.required = porSeccion;
      };
      alcance.addEventListener('change', actualizar);
      actualizar();
    }
    // Cierra el desplegable si se hace clic fuera; no cambia el calendario.
    document.addEventListener('click', evento => {
      if (!root.contains(evento.target)) menu.open = false;
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('[data-nuevo-calendario]').forEach(iniciar));
  } else {
    document.querySelectorAll('[data-nuevo-calendario]').forEach(iniciar);
  }
})();
