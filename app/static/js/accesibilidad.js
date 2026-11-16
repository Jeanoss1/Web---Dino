// Panel de accesibilidad de Dino Park.
// Opciones: lectura fácil, colores alternativos, alto contraste, tamaño del
// texto y narrador por voz (lee la descripción de las imágenes y el texto
// de la página con la Web Speech API del navegador, sin servicios externos).
// La elección se guarda en el navegador y se aplica en todas las páginas.
(function () {
  'use strict';

  const CLAVE = 'dp-accesibilidad';
  const INICIAL = { lectura: false, colores: false, contraste: false, texto: 0, narrador: false };
  const voz = window.speechSynthesis || null;
  let cfg = leer();

  function leer() {
    try {
      return Object.assign({}, INICIAL, JSON.parse(localStorage.getItem(CLAVE) || '{}'));
    } catch (e) {
      return Object.assign({}, INICIAL);
    }
  }

  function guardar() {
    try { localStorage.setItem(CLAVE, JSON.stringify(cfg)); } catch (e) { /* modo privado */ }
  }

  // Se aplica antes de pintar el panel para que la página no "parpadee"
  function aplicar() {
    const html = document.documentElement;
    html.classList.toggle('dp-lectura', cfg.lectura);
    html.classList.toggle('dp-colores', cfg.colores);
    html.classList.toggle('dp-contraste', cfg.contraste);
    html.classList.toggle('dp-narrador', cfg.narrador);
    html.classList.remove('dp-texto-1', 'dp-texto-2');
    if (cfg.texto > 0) html.classList.add('dp-texto-' + cfg.texto);
    if (cfg.lectura) cargarFuenteLectura();
  }

  function cargarFuenteLectura() {
    if (document.getElementById('dp-fuente-lexend')) return;
    const link = document.createElement('link');
    link.id = 'dp-fuente-lexend';
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Lexend:wght@400;600;700&display=swap';
    document.head.appendChild(link);
  }

  aplicar();

  // ---------- Narrador ----------

  function vozEspanol() {
    const voces = voz ? voz.getVoices() : [];
    return voces.find(v => /^es(-|_)(PE|419|MX|US)/i.test(v.lang))
      || voces.find(v => /^es/i.test(v.lang)) || null;
  }

  function hablar(texto, alTerminar) {
    if (!voz || !texto) return;
    voz.cancel();
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = 'es-PE';
    const v = vozEspanol();
    if (v) u.voice = v;
    u.rate = 0.95;
    if (alTerminar) u.onend = alTerminar;
    voz.speak(u);
  }

  function limpiarResaltado() {
    document.querySelectorAll('.dp-leyendo').forEach(e => e.classList.remove('dp-leyendo'));
    document.querySelectorAll('.dp-marco').forEach(e => e.classList.remove('dp-marco'));
  }

  // Las imágenes se marcan en su contenedor para que ninguna capa encima las tape
  function resaltar(el) {
    if (el.tagName === 'IMG' && el.parentElement && el.parentElement !== document.body) {
      el.parentElement.classList.add('dp-marco');
    } else {
      el.classList.add('dp-leyendo');
    }
  }

  function detener() {
    if (voz) voz.cancel();
    limpiarResaltado();
  }

  function textoDeImagen(img) {
    const alt = (img.getAttribute('alt') || '').trim();
    return alt ? 'Imagen: ' + alt : '';
  }

  // Con el narrador activo, las imágenes reciben foco con Tab y se leen
  // al pasar el mouse, al enfocarlas o al tocarlas en el celular.
  function prepararImagenes() {
    document.querySelectorAll('img[alt]').forEach(img => {
      if (!img.getAttribute('alt').trim() || img.closest('a, button')) return;
      if (cfg.narrador) {
        img.setAttribute('tabindex', '0');
        img.dataset.dpNarrable = '1';
      } else if (img.dataset.dpNarrable) {
        img.removeAttribute('tabindex');
        delete img.dataset.dpNarrable;
      }
    });
  }

  let ultimaImagen = null;
  function narrarImagen(img) {
    if (!cfg.narrador || img === ultimaImagen) return;
    const texto = textoDeImagen(img);
    if (!texto) return;
    ultimaImagen = img;
    detener();
    resaltar(img);
    hablar(texto, () => { limpiarResaltado(); ultimaImagen = null; });
  }

  // Busca la imagen bajo el puntero aunque la cubra una capa decorativa
  // (por ejemplo, el degradado sobre las fotos de las sedes)
  function imagenBajoPuntero(e) {
    if (e.target.closest && e.target.closest('img[alt]')) return e.target.closest('img[alt]');
    const pila = document.elementsFromPoint ? document.elementsFromPoint(e.clientX, e.clientY) : [];
    return pila.find(el => el.matches('img[alt]') && el.getAttribute('alt').trim()) || null;
  }

  document.addEventListener('mouseover', e => {
    if (!cfg.narrador) return;
    const img = imagenBajoPuntero(e);
    if (img) narrarImagen(img);
  });
  document.addEventListener('focusin', e => {
    if (e.target.matches && e.target.matches('img[alt]')) narrarImagen(e.target);
  });
  document.addEventListener('click', e => {
    if (!cfg.narrador) return;
    const img = imagenBajoPuntero(e);
    if (img) { ultimaImagen = null; narrarImagen(img); }
  });

  // Lee en orden los títulos, párrafos y descripciones de imágenes del contenido
  function leerPagina() {
    const raiz = document.querySelector('main') || document.body;
    const partes = [...raiz.querySelectorAll('h1, h2, h3, h4, p, li, img[alt]')]
      .filter(e => e.offsetParent !== null && !e.closest('.dp-a11y-panel'))
      .map(e => ({ el: e, texto: e.tagName === 'IMG' ? textoDeImagen(e) : e.textContent.replace(/\s+/g, ' ').trim() }))
      .filter(p => p.texto);
    let i = 0;
    const siguiente = () => {
      limpiarResaltado();
      if (i >= partes.length) return;
      const p = partes[i++];
      resaltar(p.el);
      p.el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      hablar(p.texto, siguiente);
    };
    siguiente();
  }

  // ---------- Panel ----------

  function crearPanel() {
    const saltar = document.createElement('a');
    saltar.className = 'dp-saltar';
    saltar.href = '#contenido';
    saltar.textContent = 'Saltar al contenido principal';
    document.body.prepend(saltar);
    const main = document.querySelector('main');
    if (main && !main.id) main.id = 'contenido';
    if (main && !main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1');

    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'dp-a11y-boton';
    boton.setAttribute('aria-label', 'Opciones de accesibilidad');
    boton.setAttribute('aria-expanded', 'false');
    boton.setAttribute('aria-controls', 'dp-a11y-panel');
    boton.innerHTML = '<span class="material-symbols-outlined" aria-hidden="true">accessibility_new</span>';

    const panel = document.createElement('div');
    panel.id = 'dp-a11y-panel';
    panel.className = 'dp-a11y-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-labelledby', 'dp-a11y-titulo');
    panel.hidden = true;
    panel.innerHTML = `
      <button type="button" class="dp-a11y-cerrar" aria-label="Cerrar opciones de accesibilidad">
        <span class="material-symbols-outlined" aria-hidden="true">close</span>
      </button>
      <h2 id="dp-a11y-titulo">Accesibilidad</h2>
      <p class="dp-ayuda">Ajusta la página a tu forma de leer. Se guarda en este navegador.</p>
      <fieldset class="dp-a11y-grupo">
        <legend>Lectura</legend>
        ${opcion('lectura', 'menu_book', 'Lectura fácil')}
        <div class="dp-a11y-fila" role="group" aria-label="Tamaño del texto">
          <button type="button" class="dp-a11y-opcion" data-texto="-1" aria-label="Reducir texto">A−</button>
          <button type="button" class="dp-a11y-opcion" data-texto="0" aria-label="Texto normal">A</button>
          <button type="button" class="dp-a11y-opcion" data-texto="1" aria-label="Aumentar texto">A+</button>
        </div>
      </fieldset>
      <fieldset class="dp-a11y-grupo">
        <legend>Color</legend>
        ${opcion('colores', 'palette', 'Colores alternativos')}
        ${opcion('contraste', 'contrast', 'Alto contraste')}
      </fieldset>
      <fieldset class="dp-a11y-grupo">
        <legend>Narrador</legend>
        ${opcion('narrador', 'record_voice_over', 'Narrador de imágenes')}
        <div class="dp-a11y-fila">
          <button type="button" class="dp-a11y-opcion" data-accion="leer">
            <span class="material-symbols-outlined" aria-hidden="true">play_arrow</span>Leer página
          </button>
          <button type="button" class="dp-a11y-opcion" data-accion="detener">
            <span class="material-symbols-outlined" aria-hidden="true">stop</span>Detener
          </button>
        </div>
      </fieldset>
      <button type="button" class="dp-a11y-opcion" data-accion="restablecer">
        <span class="material-symbols-outlined" aria-hidden="true">restart_alt</span>Restablecer
      </button>
      <p class="dp-oculto" aria-live="polite" id="dp-a11y-aviso"></p>`;

    document.body.append(boton, panel);

    const aviso = panel.querySelector('#dp-a11y-aviso');
    const anunciar = t => { aviso.textContent = ''; setTimeout(() => { aviso.textContent = t; }, 50); };

    const abrir = () => {
      panel.hidden = false;
      boton.setAttribute('aria-expanded', 'true');
      panel.querySelector('.dp-a11y-opcion').focus();
    };
    const cerrar = () => {
      panel.hidden = true;
      boton.setAttribute('aria-expanded', 'false');
      boton.focus();
    };
    boton.addEventListener('click', () => (panel.hidden ? abrir() : cerrar()));
    panel.querySelector('.dp-a11y-cerrar').addEventListener('click', cerrar);
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !panel.hidden) cerrar();
      if (e.key === 'Escape') detener();
    });

    const refrescar = () => {
      panel.querySelectorAll('[data-opcion]').forEach(b => {
        const on = !!cfg[b.dataset.opcion];
        b.setAttribute('aria-pressed', String(on));
        b.querySelector('.dp-estado').textContent = on ? 'Activado' : 'Desactivado';
      });
      panel.querySelectorAll('[data-texto]').forEach(b => {
        const n = Number(b.dataset.texto);
        b.setAttribute('aria-pressed', String(n === 0 ? cfg.texto === 0 : (n > 0 && cfg.texto > 0)));
      });
      aplicar();
      prepararImagenes();
    };

    panel.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.opcion) {
        const clave = b.dataset.opcion;
        cfg[clave] = !cfg[clave];
        if (clave === 'narrador') {
          if (!voz) { cfg.narrador = false; anunciar('Tu navegador no permite la lectura en voz alta'); }
          else hablar(cfg.narrador ? 'Narrador activado. Pasa el cursor o el foco por una imagen para escuchar su descripción.' : 'Narrador desactivado');
        }
        anunciar(b.dataset.etiqueta + (cfg[clave] ? ' activado' : ' desactivado'));
      } else if (b.dataset.texto) {
        const n = Number(b.dataset.texto);
        cfg.texto = n === 0 ? 0 : Math.max(0, Math.min(2, cfg.texto + n));
        anunciar('Tamaño de texto ' + (cfg.texto === 0 ? 'normal' : 'aumentado ' + cfg.texto));
      } else if (b.dataset.accion === 'leer') {
        if (voz) leerPagina(); else anunciar('Tu navegador no permite la lectura en voz alta');
        return;
      } else if (b.dataset.accion === 'detener') {
        detener();
        return;
      } else if (b.dataset.accion === 'restablecer') {
        detener();
        cfg = Object.assign({}, INICIAL);
        anunciar('Opciones restablecidas');
      } else {
        return;
      }
      guardar();
      refrescar();
    });

    refrescar();
  }

  function opcion(clave, icono, texto) {
    return `<button type="button" class="dp-a11y-opcion" data-opcion="${clave}" data-etiqueta="${texto}" aria-pressed="false">
      <span class="material-symbols-outlined" aria-hidden="true">${icono}</span>${texto}
      <span class="dp-estado" aria-hidden="true"></span></button>`;
  }

  if (voz && voz.onvoiceschanged !== undefined) voz.onvoiceschanged = () => {};

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', crearPanel);
  else crearPanel();
})();
