const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(id) {
    this.id = id; this.dataset = {}; this.attrs = {};
    this.listeners = {}; this.value = ''; this.textContent=''; this.hidden=false;
    this.style={}; this.disabled=false;
  }
  addEventListener(type, handler) { (this.listeners[type]??=[]).push(handler); }
  emit(type) { for(const h of this.listeners[type] || [])h({ preventDefault(){} }); }
  getAttribute(name) { return this.attrs[name] || ''; }
  setAttribute(name, value) { this.attrs[name]=value; }
  removeAttribute(name) { delete this.attrs[name]; }
  checkValidity() { return true; }
  replaceChildren() { this.children=[]; }
  append(...children) { this.children??=[];this.children.push(...children); }
}
const ids=['registro-unificado','rol-registro','paso-volver','paso-continuar',
  'confirmar-registro','form-registro-unificado','error-registro',
  'feedback-rut','feedback-email','feedback-password2','seguridad-clave-nivel',
  'seguridad-clave','dominio-ayuda','resumen-registro','paso-indicador','progreso-registro',
  'id_rut','id_first_name','id_apellidos','id_telefono','id_email','id_password1','id_password2'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
const roles=['estudiante','docente','administrativo'].map(role=>{
  const button=new Element('role-'+role);button.dataset.role=role;return button;
});
const steps=[1,2,3].map(n=>{const s=new Element('step-'+n);s.dataset.step=String(n);return s;});
elements['registro-unificado'].dataset={dominios:JSON.stringify({estudiante:'duocuc.cl',docente:'gmail.com',administrativo:'gmail.com'}),errorServidor:'no'};
elements['registro-unificado'].querySelectorAll=selector=>selector==='[data-role]'?roles:selector==='[data-step]'?steps:[];
const document={getElementById:id=>elements[id]||null,createElement:tag=>new Element(tag)};
const window={EduNovaRegistroValidacion:{
  rut:v=>v==='12345678-5',
  correo:(v,r,d)=>v.toLowerCase().endsWith('@'+d[r]),
  clave:v=>({accepted:v.length>=8,level:v.length>=12?'fuerte':'media'})
}};
const js=fs.readFileSync(path.join(__dirname,'../../static/js/registro-guiado-simple.js'),'utf8');
vm.runInNewContext(js,{document,window,console});
const click=(button)=>button.emit('click');
const setInput=(id,value)=>{elements[id].value=value;elements['form-registro-unificado'].emit('input');};
click(roles[0]);click(elements['paso-continuar']);
setInput('id_rut','12345678-5');setInput('id_first_name','Nombre');setInput('id_apellidos','Apellido');
setInput('id_email','alumno@duocuc.cl');setInput('id_password1','ClaveSegura123!');
setInput('id_password2','ClaveSegura123!');
assert.equal(elements['paso-continuar'].disabled,false);
click(elements['paso-continuar']); // Paso 3 con datos
click(elements['paso-volver']); // Regresa a paso 2 y debe borrar todo
for(const campo of ['rut','first_name','apellidos','telefono','email','password1','password2']){
  assert.equal(elements['id_'+campo].value,'',`El campo ${campo} no se borró al volver`);
}
click(elements['paso-volver']); // Regresa a selección de rol
assert.equal(elements['rol-registro'].value,'');
click(roles[1]);click(elements['paso-continuar']);
assert.equal(elements['id_email'].value,'');
assert.equal(elements['paso-continuar'].disabled,true);
console.log('OK: volver y cambiar de rol borran los datos personales del registro.');
