/* Calendario EduNova. Sin peticiones nuevas: utiliza el calendario privado
   que Django ya entrega y sobrevive a cambios de mes con HTMX. */
(function () {
  'use strict';
  if (window.EduNovaCalendarioDetalle) {
    window.EduNovaCalendarioDetalle.iniciarTodos();
    return;
  }
  const tipos = {
    clase: {nombre:'Clase', token:'--edn-class'},
    tarea: {nombre:'Tarea', token:'--edn-task'},
    reunion: {nombre:'Reunión', token:'--edn-meeting'},
    evento: {nombre:'Evento', token:'--edn-event'},
    evaluacion: {nombre:'Evaluación', token:'--edn-exam'},
    otro: {nombre:'Evento', token:'--edn-event'}
  };
  // Un único estado por página; la selección se conserva entre cambios de mes.
  const estado = {fecha:null};
  const abrir = elemento => elemento && !elemento.hidden;
  const detalle = (elem, selector) => elem.querySelector(selector)?.textContent.trim() || '';
  const color = (raiz, tipo) => {
    const info = tipos[tipo] || tipos.evento;
    return getComputedStyle(raiz).getPropertyValue(info.token).trim() || '#829fbc';
  };
  const nombre = tipo => (tipos[tipo] || tipos.evento).nombre;

  function entradas(dia) {
    return [...dia.querySelectorAll('.edn-calendar-entry')].map(registro => ({
      tipo: registro.dataset.kind in tipos ? registro.dataset.kind : 'evento',
      hora:registro.dataset.time || '',
      rango:registro.dataset.range || '',
      titulo:detalle(registro,'.edn-entry-title'),
      descripcion:detalle(registro,'.edn-entry-description'),
      meta:detalle(registro,'.edn-entry-meta')
    })).sort((a,b) => (a.hora || '99:99').localeCompare(b.hora || '99:99', 'es'));
  }

  function elemento(tag, clase, valor) {
    const e = document.createElement(tag);
    if (clase) e.className=clase;
    if (valor !== undefined) e.textContent=valor;
    return e;
  }

  function dibujarDias(raiz) {
    raiz.querySelectorAll('.edn-calendar-date').forEach(dia => {
      const items = entradas(dia);
      const dots = dia.querySelector('.edn-day-dots');
      const minis = dia.querySelector('.edn-day-minis');
      dots.replaceChildren();
      minis.replaceChildren();
      const vistos = new Set();
      for (const item of items) {
        const tipo = item.tipo === 'otro' ? 'evento' : item.tipo;
        if (vistos.has(tipo)) continue;
        vistos.add(tipo);
        if (vistos.size <= 3) {
          const dot = elemento('span','edn-dot edn-dot-'+tipo);
          dots.appendChild(dot);
        }
      }
      if (vistos.size > 3) dots.appendChild(elemento('span','edn-dot-count','+'+(vistos.size-3)));
      const boton = dia.querySelector('[data-edn-day]');
      if (boton) boton.setAttribute('aria-label',boton.getAttribute('aria-label')+'. '+items.length+' actividades');
      items.slice(0,2).forEach(item => {
        const mini = elemento('span','edn-mini');
        mini.style.setProperty('--edn-mini-color',color(raiz,item.tipo));
        mini.appendChild(elemento('span','edn-mini-time',item.rango || 'Sin hora'));
        mini.appendChild(elemento('span','edn-mini-name',item.titulo));
        minis.appendChild(mini);
      });
      if (items.length > 2) minis.appendChild(elemento('span','edn-mini-more',`+${items.length-2} actividades más`));
    });
  }

  function fechaInicial(raiz) {
    const botones=[...raiz.querySelectorAll('[data-edn-day]')];
    if (!botones.length) return null;
    if (botones.some(b=>b.dataset.ednDay === estado.fecha)) return estado.fecha;
    const hoy=botones.find(b=>b.classList.contains('edn-is-today'));
    if (hoy) return hoy.dataset.ednDay;
    const conActividad=botones.find(b=>entradas(b.closest('.edn-calendar-date')).length>0);
    return (conActividad || botones[0]).dataset.ednDay;
  }

  function dibujarDetalle(raiz) {
    const panel=raiz.querySelector('.edn-calendar-detail');
    const fecha=estado.fecha;
    if (!panel || !fecha) return;
    const boton=[...raiz.querySelectorAll('[data-edn-day]')].find(b=>b.dataset.ednDay===fecha);
    if (!boton) return;
    const items=entradas(boton.closest('.edn-calendar-date'));
    let encabezado=fecha;
    try {
      const f=new Date(`${fecha}T12:00:00`);
      encabezado=new Intl.DateTimeFormat('es-CL', {weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(f);
    } catch (_e) {}
    panel.querySelector('[data-edn-detail-title]').textContent=encabezado;
    panel.querySelector('[data-edn-detail-count]').textContent=items.length === 1 ? '1 actividad agendada' : `${items.length} actividades agendadas`;
    const lista=panel.querySelector('[data-edn-detail-items]');
    lista.replaceChildren();
    if (!items.length) {
      lista.appendChild(elemento('p','edn-detail-empty','Sin actividades para esta fecha. Puedes elegir otro día del calendario.'));
      return;
    }
    items.forEach(item=>{
      const card=elemento('article','edn-detail-card');
      card.style.setProperty('--edn-item-color',color(raiz,item.tipo));
      card.appendChild(elemento('p','edn-detail-type',`${nombre(item.tipo)} · ${item.rango || 'Sin hora'}`));
      card.appendChild(elemento('h5',null,item.titulo));
      if(item.meta)card.appendChild(elemento('p','edn-detail-meta',item.meta));
      if(item.descripcion)card.appendChild(elemento('p','edn-detail-description',item.descripcion));
      lista.appendChild(card);
    });
  }

  function actualizarSeleccion(raiz) {
    raiz.querySelectorAll('[data-edn-day]').forEach(boton => {
      boton.setAttribute('aria-pressed',String(boton.dataset.ednDay===estado.fecha));
    });
    dibujarDetalle(raiz);
  }

  function sincronizarAmpliacion() {
    const grid=document.getElementById('portal-estudiante-grid');
    const ampliado=Boolean(grid && grid.classList.contains('edunova-calendar-expanded'));
    document.querySelectorAll('[data-edn-calendar]').forEach(raiz => {
      const panel=raiz.querySelector('.edn-calendar-detail');
      if(panel)panel.hidden=!ampliado;
      if(!estado.fecha || !raiz.querySelector(`[data-edn-day="${estado.fecha}"]`))estado.fecha=fechaInicial(raiz);
      actualizarSeleccion(raiz);
    });
  }

  function iniciar(raiz) {
    if (raiz.dataset.ednIniciado==='si') return;
    raiz.dataset.ednIniciado='si';
    dibujarDias(raiz);
    if (!estado.fecha || ![...raiz.querySelectorAll('[data-edn-day]')].some(b=>b.dataset.ednDay===estado.fecha)) {
      estado.fecha=fechaInicial(raiz);
    }
    sincronizarAmpliacion();
  }
  function iniciarTodos() {document.querySelectorAll('[data-edn-calendar]').forEach(iniciar);}

  // Se usa delegación para que HTMX pueda sustituir el calendario sin perder eventos.
  document.addEventListener('click', event=>{
    const dia=event.target.closest?.('[data-edn-day]');
    if(dia){
      const raiz=dia.closest('[data-edn-calendar]');
      if(!raiz)return;
      estado.fecha=dia.dataset.ednDay;
      actualizarSeleccion(raiz);
    }
    if(event.target.closest?.('#calendario-expandir')) {
      // El controlador existente del portal alterna esta clase en el botón.
      // En fase de burbujeo ya podemos leer el estado actualizado.
      sincronizarAmpliacion();
    }
  });
  document.addEventListener('htmx:afterSwap',()=>iniciarTodos());
  document.addEventListener('htmx:historyRestore',()=>iniciarTodos());
  window.EduNovaCalendarioDetalle={iniciarTodos};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',iniciarTodos,{once:true});
  else iniciarTodos();
})();
