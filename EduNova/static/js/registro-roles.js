/* Registro por rol. Las selecciones se comprueban nuevamente en Django. */
(() => {
  'use strict';
  const root = document.getElementById('registro-unificado');
  if (!root) return;
  const readJSON = id => JSON.parse(document.getElementById(id).textContent);
  const previous = readJSON('registro-previo');
  const catalogs = readJSON('catalogo-onboarding');
  const careers = readJSON('carreras-onboarding');
  const mentions = readJSON('menciones-onboarding');
  const semester = readJSON('semestre-onboarding');
  const currentYear = readJSON('anio-onboarding');
  const $ = id => document.getElementById(id);
  const roleField = $('rol-registro');
  const selectedCareers = new Set(previous.carreras || []);
  const selectedSections = new Set(previous.secciones || []);
  const selectedSubjects = new Set(previous.asignaturas || []);
  const selectedMentions = new Set(previous.menciones_docente || []);
  let role = roleField.value || '';
  let step = 1;
  const sequence = () => role === 'administrativo' ? [1, 2, 4, 5] : [1, 2, 3, 4, 5];
  const error = message => { $('error-registro').textContent = message || ''; };
  const label = (text, className = '') => {
    const el = document.createElement('span'); el.textContent = text; el.className = className; return el;
  };
  function itemBox(title, subtitle) {
    const box = document.createElement('div'); box.className = 'registro-resumen-item';
    box.append(label(title, 'font-semibold'));
    if (subtitle) box.append(label(subtitle, 'text-sm text-muted block mt-1'));
    return box;
  }
  function showStep(next) {
    step = next;
    root.querySelectorAll('[data-step]').forEach(el => { el.hidden = Number(el.dataset.step) !== step; });
    root.querySelectorAll('[data-only]').forEach(el => {
      el.hidden = el.dataset.only !== role || (step !== 2 && step !== 3);
    });
    const flow = sequence();
    const index = flow.indexOf(step) + 1;
    $('paso-indicador').textContent = `Paso ${index} de ${flow.length}`;
    $('progreso-registro').style.width = `${100 * index / flow.length}%`;
    $('paso-volver').hidden = step === 1;
    $('paso-continuar').hidden = step === 5;
    $('confirmar-registro').hidden = step !== 5;
    const desc = {
      estudiante: 'Elige tu carrera, modalidad y año de ingreso para sugerirte asignaturas.',
      docente: 'Puedes impartir clases en varias carreras. Selecciónalas para ver las asignaturas.',
      administrativo: 'Selecciona tu escuela y todas las carreras que diriges.',
    };
    $('ayuda-academica').textContent = desc[role] || '';
    $('descripcion-seleccion').textContent = role === 'docente'
      ? 'Abre cada asignatura, selecciónala y marca una o más secciones que impartes.'
      : 'Abre una asignatura y selecciona una sección. También puedes personalizar la malla.';
    error('');
    if (step === 5) renderSummary();
    const heading = root.querySelector(`[data-step="${step}"] h2`);
    if (heading) heading.setAttribute('tabindex', '-1');
  }
  function selectRole(nextRole, preserve = false) {
    if (!preserve && nextRole !== role) {
      selectedCareers.clear(); selectedSections.clear(); selectedSubjects.clear(); selectedMentions.clear();
      $('carrera_id').value = ''; $('modalidad-estudiante').value = ''; $('anio_ingreso').value = '';
      $('escuela-registro').value = '';
      $('personalizar-asignaturas').checked = false;
    }
    role = nextRole;
    roleField.value = nextRole;
    root.querySelectorAll('[data-role]').forEach(el => {
      el.setAttribute('aria-pressed', String(el.dataset.role === role));
    });
    if (role === 'docente') {
      renderCareerOptions('carreras-docente', careers);
      renderTeacherMentions();
    }
    if (role === 'administrativo') renderDirectorCareers();
  }
  function renderCareerOptions(containerId, options) {
    const rootList = $(containerId); rootList.replaceChildren();
    if (!options.length) { rootList.append(label('No hay carreras disponibles.', 'text-muted text-sm')); return; }
    for (const career of options) {
      const row = document.createElement('label'); row.className = 'registro-opcion';
      const input = document.createElement('input');
      input.type = 'checkbox'; input.name = 'carreras'; input.value = career.id;
      input.checked = selectedCareers.has(String(career.id));
      input.addEventListener('change', () => {
        if (input.checked) selectedCareers.add(String(career.id));
        else selectedCareers.delete(String(career.id));
        selectedSections.clear(); selectedSubjects.clear();
        if (containerId === 'carreras-docente') renderTeacherMentions();
      });
      const text = document.createElement('span');
      text.append(label(career.nombre, 'font-medium block'));
      if (containerId === 'carreras-docente') text.append(label(career.escuela, 'text-muted text-xs block'));
      row.append(input, text); rootList.append(row);
    }
  }
  function mentionsForCareer(careerId) {
    return mentions.filter(m => String(m.carrera_id) === String(careerId));
  }
  function renderTeacherMentions() {
    const holder = $('menciones-docente'); holder.replaceChildren();
    const active = careers.filter(c => selectedCareers.has(String(c.id)));
    const valid = new Set(active.flatMap(c => mentionsForCareer(c.id).map(m => String(m.id))));
    for (const id of [...selectedMentions]) if (!valid.has(id)) selectedMentions.delete(id);
    let hasMentions = false;
    for (const career of active) {
      const choices = mentionsForCareer(career.id);
      if (!choices.length) continue;
      hasMentions = true;
      const group = document.createElement('fieldset'); group.className = 'registro-mencion-grupo';
      const legend = document.createElement('legend'); legend.className = 'font-semibold'; legend.textContent = career.nombre;
      group.append(legend);
      const list = document.createElement('div'); list.className = 'registro-opciones mt-2';
      for (const m of choices) {
        const row = document.createElement('label'); row.className = 'registro-opcion';
        const input = document.createElement('input'); input.type = 'checkbox';
        input.name = 'menciones_docente'; input.value = String(m.id);
        input.checked = selectedMentions.has(String(m.id));
        input.addEventListener('change', () => {
          if (input.checked) selectedMentions.add(String(m.id));
          else selectedMentions.delete(String(m.id));
          selectedSections.clear(); selectedSubjects.clear();
        });
        row.append(input, label(m.nombre)); list.append(row);
      }
      group.append(list); holder.append(group);
    }
    if (!hasMentions) holder.append(label(
      active.length ? 'Las carreras seleccionadas todavía no tienen menciones registradas; puedes continuar.'
                    : 'Selecciona primero una o varias carreras.',
      'text-muted text-sm'));
  }
  function renderDirectorCareers() {
    const school = $('escuela-registro').value;
    const visible = careers.filter(c => c.escuela === school);
    for (const id of Array.from(selectedCareers)) {
      if (!visible.some(c => String(c.id) === id)) selectedCareers.delete(id);
    }
    renderCareerOptions('carreras-director', visible);
  }
  const selectedCareerIds = () => role === 'estudiante' ? [$('carrera_id').value] : [...selectedCareers];
  function availableSubjects() {
    const academicYear = currentYear - Number($('anio_ingreso').value) + 1;
    const all = new Map();
    for (const careerId of selectedCareerIds()) {
      const rows = catalogs[careerId] || [];
      const versiones = role === 'estudiante'
        ? rows.filter(s => s.cohorte === Number($('anio_ingreso').value)) : [];
      const candidatos = role === 'estudiante' && versiones.length ? versiones :
        rows.filter(s => s.cohorte === null || s.cohorte === undefined);
      for (const subject of candidatos) {
        const specific = subject.mencion !== null && subject.mencion !== undefined;
        if (specific && role === 'docente' &&
            !selectedMentions.has(String(subject.mencion))) continue;
        if (role === 'estudiante' && semester && !$('personalizar-asignaturas').checked &&
            (subject.anio !== academicYear || subject.semestre !== semester)) continue;
        // La modalidad se filtra por sección, no por asignatura.
        const selectedMode = $('modalidad-estudiante').value;
        const visible = role === 'estudiante'
          ? {...subject, secciones: subject.secciones.filter(s => s.modalidad === selectedMode)}
          : subject;
        if (!all.has(String(visible.id))) all.set(String(visible.id), visible);
      }
    }
    return [...all.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
  }
  function renderSubjects() {
    const holder = $('asignaturas-lista'); holder.replaceChildren();
    const list = availableSubjects();
    if (!list.length) {
      const message = role === 'estudiante'
        ? 'No hay asignaturas disponibles según el año y semestre seleccionados. Prueba «Personalizar» para revisar toda la malla.'
        : 'No hay asignaturas disponibles para las carreras elegidas.';
      holder.append(itemBox(message)); return;
    }
    for (const subject of list) {
      const panel = document.createElement('details'); panel.className = 'registro-asignatura';
      const heading = document.createElement('summary');
      heading.className = 'registro-asignatura-titulo';
      const titleWrap = document.createElement('span');
      titleWrap.append(label(`${subject.codigo} · ${subject.nombre}`, 'font-semibold block'));
      if (role === 'estudiante') titleWrap.append(label(
        `${subject.anio ? subject.anio + '° año' : 'Año por confirmar'} · ${subject.semestre ? subject.semestre + '° semestre' : 'Semestre por confirmar'}`,
        'text-muted text-xs block mt-1'));
      if (role === 'docente') {
        const chooser = document.createElement('label'); chooser.className = 'registro-asignatura-check';
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = 'asignaturas';
        checkbox.value = String(subject.id); checkbox.checked = selectedSubjects.has(String(subject.id));
        checkbox.addEventListener('click', ev => ev.stopPropagation());
        checkbox.addEventListener('change', () => {
          if (checkbox.checked) { selectedSubjects.add(String(subject.id)); panel.open = true; }
          else {
            selectedSubjects.delete(String(subject.id));
            subject.secciones.forEach(s => selectedSections.delete(String(s.id)));
          }
          panel.querySelectorAll('.registro-seccion input').forEach(input => {
            input.disabled = !checkbox.checked;
            if (!checkbox.checked) input.checked = false;
          });
        });
        chooser.append(checkbox, label('Imparto esta asignatura', 'text-sm'));
        const head = document.createElement('span'); head.append(titleWrap, chooser); heading.append(head);
      } else heading.append(titleWrap);
      panel.append(heading);
      if (!subject.secciones.length) panel.append(label(role === 'estudiante' ? 'No hay secciones de la modalidad seleccionada para esta asignatura.' : 'No hay secciones registradas.', 'text-muted text-sm block p-3'));
      for (const section of subject.secciones) {
        const row = document.createElement('label'); row.className = 'registro-seccion';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.name = 'secciones'; input.value = String(section.id);
        input.checked = selectedSections.has(String(section.id));
        input.disabled = role === 'docente' && !selectedSubjects.has(String(subject.id));
        input.addEventListener('change', () => {
          if (role === 'estudiante') {
            subject.secciones.forEach(s => selectedSections.delete(String(s.id)));
            if (input.checked) selectedSections.add(String(section.id));
            panel.querySelectorAll('.registro-seccion input').forEach(other => {
              if (other !== input) other.checked = false;
            });
          } else if (input.checked) selectedSections.add(String(section.id));
          else selectedSections.delete(String(section.id));
          // No reconstruir el acordeón: se conserva el foco y el estado abierto.
        });
        const text = document.createElement('span');
        text.append(label(section.codigo, 'font-semibold block'));
        text.append(label(`Docente: ${section.docentes.join(', ')} · Horario: ${section.horarios.join('; ')}`, 'text-muted text-xs block mt-1'));
        row.append(input, text); panel.append(row);
      }
      if (subject.secciones.some(s => selectedSections.has(String(s.id)))) panel.open = true;
      holder.append(panel);
    }
  }
  function validateStep() {
    if (step === 1) return role ? '' : 'Selecciona primero si eres estudiante, docente o director de carrera.';
    if (step === 2) {
      if (role === 'estudiante') {
        if (!$('carrera_id').value) return 'Selecciona tu carrera.';
        if (!$('modalidad-estudiante').value) return 'Selecciona tu modalidad: Diurno o Vespertino.';
        return $('anio_ingreso').value ? '' : 'Selecciona tu año de ingreso.';
      }
      if (role === 'administrativo' && !$('escuela-registro').value) return 'Selecciona la escuela.';
      if (!selectedCareers.size) return 'Selecciona al menos una carrera.';
      if (role === 'docente') {
        for (const careerId of selectedCareers) {
          const list = mentionsForCareer(careerId);
          if (list.length && !list.some(m => selectedMentions.has(String(m.id))))
            return 'Selecciona al menos una mención de cada carrera que tenga menciones registradas.';
        }
      }
      return '';
    }
    if (step === 3) {
      const options = availableSubjects();
      const validSectionIds = new Set(options.flatMap(s => s.secciones.map(sec => String(sec.id))));
      for (const id of [...selectedSections]) if (!validSectionIds.has(id)) selectedSections.delete(id);
      if (!selectedSections.size) return 'Selecciona al menos una sección.';
      if (role === 'docente') {
        if (!selectedSubjects.size) return 'Selecciona una o más asignaturas.';
        for (const id of selectedSubjects) {
          const subject = options.find(s => String(s.id) === id);
          if (!subject || !subject.secciones.some(s => selectedSections.has(String(s.id)))) {
            return 'Cada asignatura seleccionada debe tener al menos una sección.';
          }
        }
      }
      return '';
    }
    if (step === 4) {
      for (const input of root.querySelectorAll('[data-step="4"] input')) {
        if (!input.checkValidity()) { input.reportValidity(); return 'Completa los datos requeridos.'; }
      }
      if ($('id_password1')?.value !== $('id_password2')?.value) return 'Las contraseñas no coinciden.';
    }
    return '';
  }
  function renderSummary() {
    const target = $('resumen-registro'); target.replaceChildren();
    const name = {estudiante:'Estudiante', docente:'Docente', administrativo:'Director de carrera'}[role];
    target.append(itemBox(`Perfil: ${name}`));
    if (role === 'estudiante') {
      const career = careers.find(c => String(c.id) === $('carrera_id').value);
      const mode = $('modalidad-estudiante').value === 'diurno' ? 'Diurno' : 'Vespertino';
      target.append(itemBox(`Carrera: ${career?.nombre || 'Sin seleccionar'}`,
        `Modalidad: ${mode} · Ingreso: ${$('anio_ingreso').value}`));
    } else {
      target.append(itemBox(role === 'administrativo' ? `Escuela: ${$('escuela-registro').value}` : 'Carreras donde impartes clases',
        careers.filter(c => selectedCareers.has(String(c.id))).map(c => c.nombre).join(' · ')));
      if (role === 'docente') target.append(itemBox('Menciones donde impartes clases',
        mentions.filter(m => selectedMentions.has(String(m.id))).map(m => m.nombre).join(' · ') || 'Sin menciones registradas'));
    }
    if (role !== 'administrativo') {
      const options = availableSubjects();
      let amount = 0;
      for (const subject of options) {
        for (const section of subject.secciones) {
          if (!selectedSections.has(String(section.id))) continue;
          amount++;
          target.append(itemBox(`${subject.codigo} · ${subject.nombre} — ${section.codigo}`,
            `Docente: ${section.docentes.join(', ')} · Horario: ${section.horarios.join('; ')}`));
        }
      }
      if (!amount) target.append(itemBox('No hay secciones seleccionadas.'));
    }
    const nombre = $('id_first_name')?.value || '';
    const apellidos = $('id_apellidos')?.value || '';
    target.append(itemBox(`${nombre} ${apellidos}`.trim(), $('id_email')?.value || ''));
  }
  root.querySelectorAll('[data-role]').forEach(button => {
    button.addEventListener('click', () => { selectRole(button.dataset.role); showStep(1); });
  });
  $('carrera_id').addEventListener('change', () => {
    selectedSections.clear(); selectedSubjects.clear();
  });
  $('modalidad-estudiante').addEventListener('change', () => {
    selectedSections.clear(); selectedSubjects.clear();
  });
  $('escuela-registro').addEventListener('change', () => {
    selectedCareers.clear(); renderDirectorCareers();
  });
  $('personalizar-asignaturas').addEventListener('change', () => {
    selectedSections.clear(); renderSubjects();
  });
  $('paso-volver').addEventListener('click', () => {
    const flow = sequence(); showStep(flow[flow.indexOf(step) - 1]);
  });
  $('paso-continuar').addEventListener('click', () => {
    const err = validateStep(); if (err) { error(err); return; }
    const flow = sequence();
    const next = flow[flow.indexOf(step) + 1];
    if (step === 2 && next === 3) {
      selectedSections.clear(); selectedSubjects.clear();
      const load = $('carga-asignaturas'); load.hidden = false;
      window.setTimeout(() => {
        renderSubjects(); load.hidden = true; showStep(next);
      }, 400);
    } else showStep(next);
  });
  root.querySelector('form').addEventListener('submit', event => {
    if (step !== 5) { event.preventDefault(); error('Revisa tu información antes de crear la cuenta.'); return; }
    if (!role) { event.preventDefault(); error('Selecciona tu tipo de cuenta.'); }
  });
  const initialRole = ['estudiante','docente','administrativo'].includes(role) ? role : '';
  role = '';
  if (initialRole) selectRole(initialRole, true);
  showStep(1);
})();
