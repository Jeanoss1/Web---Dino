// Añade el token CSRF a todas las peticiones fetch que modifican datos.
(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta) return;
  var token = meta.getAttribute('content');
  var original = window.fetch;
  window.fetch = function (url, opciones) {
    opciones = opciones || {};
    var metodo = (opciones.method || 'GET').toUpperCase();
    if (metodo !== 'GET' && metodo !== 'HEAD') {
      var cabeceras = new Headers(opciones.headers || {});
      cabeceras.set('X-CSRFToken', token);
      opciones.headers = cabeceras;
    }
    return original(url, opciones);
  };
})();
