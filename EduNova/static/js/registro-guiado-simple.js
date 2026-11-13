/* Restauración del control de paso del 10-11-2026; sin dependencias de mallas. */
(() => {
  'use strict';
  const root = document.getElementById('registro-unificado');
  if (!root) return;
  const val = window.EduNovaRegistroValidacion;
  const $ = id => document.getElementById(id);
  if (!val) { console.error('Falta el validador de registro'); return; }
  const domains = JSON.parse(root.dataset.dominios);
  const roleInput = $('rol-registro');
  const back = $('paso-volver');
  const next = $('paso-continuar');
  const finish = $('confirmar-registro');
  const form = $('form-registro-unificado');
  const alert = $('error-registro');
  let step = root.dataset.errorServidor === 'si' ? 2 : 1;
  function status(id, input, type, message) {
    const target = $(id); if (!target) return;
    target.textContent = message; target.dataset.status = type;
    if (input) {
      if (type === 'error') input.setAttribute('aria-invalid','true');
      else input.removeAttribute('aria-invalid');
      const old = (input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
      if (!old.includes(id)) input.setAttribute('aria-describedby', [...old,id].join(' '));
    }
  }
  function validAccount(show) {
    const role=roleInput.value;
    const rut=$('id_rut'), mail=$('id_email'), pass=$('id_password1');
    const confirm=$('id_password2'), first=$('id_first_name'), last=$('id_apellidos');
    const phone=$('id_telefono');
    if (![rut,mail,pass,confirm,first,last].every(Boolean)) return false;
    const rutOk=val.rut(rut.value);
    const mailOk=val.correo(mail.value,role,domains);
    const pw=val.clave(pass.value);
    const match=Boolean(confirm.value && pass.value && confirm.value===pass.value);
    if (show) {
      status('feedback-rut',rut,rut.value ? rutOk?'ok':'error':'', !rut.value?'':rutOk?'✓ RUT válido.':'RUT inválido: verifica el dígito verificador.');
      const domain=domains[role] || 'institucional';
      status('feedback-email',mail,mail.value ? mailOk?'ok':'error':'', !mail.value?'':mailOk?'✓ Correo electrónico válido.':`El correo debe terminar exactamente en @${domain}.`);
      status('feedback-password2',confirm,confirm.value ? match?'ok':'error':'',!confirm.value?'':match?'✓ Las contraseñas coinciden.':'Las contraseñas no coinciden.');
      const meter=$('seguridad-clave-nivel');
      if (meter) { meter.dataset.level=pw.level;meter.style.width= !pass.value?'0%':pw.level==='fuerte'?'100%':pw.level==='media'?'65%':'25%'; }
      const tip=$('seguridad-clave');
      if (tip) tip.textContent=!pass.value?'Mínimo 8 caracteres y dos tipos de caracteres.': pw.accepted?'✓ Contraseña aceptada.':'La contraseña debe tener 8 caracteres y combinar al menos dos tipos.';
      $('dominio-ayuda').textContent=role ? `Dominio requerido para tu perfil: @${domain}` : '';
    }
    return Boolean(role && rutOk && mailOk && pw.accepted && match &&
        first.value.trim() && last.value.trim() &&
        [rut,mail,pass,confirm,first,last,phone].filter(Boolean).every(e=>e.checkValidity()));
  }
  function summary() {
    const data = [
      ['Tipo de cuenta', ({estudiante:'Estudiante',docente:'Docente',administrativo:'Director de carrera'})[roleInput.value]||''],
      ['RUT',$('id_rut').value], ['Nombre', $('id_first_name').value+' '+$('id_apellidos').value],
      ['Teléfono', $('id_telefono')?.value || 'No informado'], ['Correo electrónico', $('id_email').value]
    ];
    const container=$('resumen-registro');container.replaceChildren();
    for (const [key,value] of data) {
      const row=document.createElement('div');row.className='registro-resumen-item';
      const dt=document.createElement('dt');dt.className='font-semibold';dt.textContent=key;
      const dd=document.createElement('dd');dd.textContent=value;row.append(dt,dd);container.append(row);
    }
  }
  function refresh() {
    root.querySelectorAll('[data-step]').forEach(section=>{section.hidden=Number(section.dataset.step)!==step;});
    root.querySelectorAll('[data-role]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.role===roleInput.value)));
    $('paso-indicador').textContent=`Paso ${step} de 3`;
    $('progreso-registro').style.width=`${step*100/3}%`;
    back.hidden=step===1;next.hidden=step===3;finish.hidden=step!==3;
    const ok=step===1?Boolean(roleInput.value):validAccount(true);
    next.disabled=!ok;finish.disabled=!validAccount(false);
    if (step===3) summary();
    if (alert) {alert.hidden=true;alert.textContent='';}
  }
  function fail(message) {alert.hidden=false;alert.textContent=message;}
  root.querySelectorAll('[data-role]').forEach(button=>button.addEventListener('click',()=>{
    roleInput.value=button.dataset.role;
    refresh();
  }));
  next.addEventListener('click',()=>{
    if (step===1 && !roleInput.value) return fail('Selecciona un tipo de cuenta.');
    if (step===2 && !validAccount(true)) return fail('Revisa los campos marcados antes de continuar.');
    if (step<3)step+=1;refresh();
  });
  back.addEventListener('click',()=>{ if(step>1) step-=1;refresh(); });
  form.addEventListener('input',refresh);
  form.addEventListener('change',refresh);
  form.addEventListener('submit',event=>{
    if (!roleInput.value || !validAccount(true) || step!==3) {
      event.preventDefault(); step=2; refresh(); fail('Completa correctamente todos los campos antes de crear tu cuenta.');
    }
  });
  refresh();
})();
