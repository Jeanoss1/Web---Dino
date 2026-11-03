// Utilidades compartidas por admin_cuadre.html y admin_reportes.html.
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const soles = n => 'S/ ' + Number(n).toFixed(2);

async function cargarSedes() {
  const res = await fetch('/api/admin/sedes', { credentials: 'same-origin' });
  const sedes = await res.json();
  $('filtro-sede').innerHTML += sedes.map(s => `<option value="${s.id_sucursal}">${esc(s.nombre)}</option>`).join('');
}
