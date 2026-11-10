/* Validador visible de registro. El servidor Django vuelve a validar siempre. */
(function (root) {
  'use strict';
  function rut(raw) {
    const text = String(raw || '').trim().toUpperCase();
    if (!/^(?:[0-9]{7,8}|[0-9]{1,2}\.[0-9]{3}\.[0-9]{3})-[0-9K]$/.test(text)) return false;
    const [number, digit] = text.replace(/\./g, '').split('-');
    if (Number(number) <= 0) return false;
    let total = 0;
    [...number].reverse().forEach((d, i) => { total += Number(d) * [2, 3, 4, 5, 6, 7][i % 6]; });
    const remaining = 11 - (total % 11);
    const correct = remaining === 11 ? '0' : remaining === 10 ? 'K' : String(remaining);
    return digit === correct;
  }
  function correo(raw, role, domains) {
    const text = String(raw || '').trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) return false;
    const required = domains && domains[role];
    return Boolean(required) && text.slice(text.lastIndexOf('@') + 1) === String(required).toLowerCase();
  }
  function clave(raw) {
    const text = String(raw || '');
    const types = [/\p{Ll}/u, /\p{Lu}/u, /\p{N}/u, /[^\p{L}\p{N}\s]/u]
      .reduce((n, pattern) => n + Number(pattern.test(text)), 0);
    const accepted = text.length >= 8 && types >= 2;
    const strong = accepted && text.length >= 12 && types >= 3;
    return {accepted, level: !accepted ? 'debil' : strong ? 'fuerte' : 'media', types};
  }
  const api = {rut, correo, clave};
  root.EduNovaRegistroValidacion = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
