// Código compartido por todas las páginas que incluyen _head.html.

// --- Protección CSRF ---
// Flask-WTF exige el token en toda petición que modifica datos. En vez de
// tocar cada fetch(), se agrega aquí la cabecera X-CSRFToken a las peticiones
// POST/PUT/PATCH/DELETE hechas al mismo sitio.
(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta || !window.fetch) return;
  const token = meta.content;
  const fetchOriginal = window.fetch.bind(window);
  const SEGUROS = ['GET', 'HEAD', 'OPTIONS', 'TRACE'];

  window.fetch = function (recurso, opciones = {}) {
    const esRequest = recurso instanceof Request;
    const metodo = (opciones.method || (esRequest ? recurso.method : 'GET')).toUpperCase();
    const url = new URL(esRequest ? recurso.url : String(recurso), location.href);
    if (SEGUROS.includes(metodo) || url.origin !== location.origin) {
      return fetchOriginal(recurso, opciones);
    }
    const cabeceras = new Headers(opciones.headers || (esRequest ? recurso.headers : undefined));
    cabeceras.set('X-CSRFToken', token);
    return fetchOriginal(recurso, { ...opciones, headers: cabeceras });
  };
})();

// Cobra una venta ya registrada (caja de entradas y caja de flota).
// Devuelve { res, json } igual que el fetch que reemplaza.
async function pagarVenta(idVenta, metodoPago) {
  const res = await fetch(`/api/ventas/${idVenta}/pago`, {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ metodo_pago: metodoPago }),
  });
  const json = await res.json();
  return { res, json };
}
