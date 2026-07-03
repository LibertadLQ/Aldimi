/* ═══════════════════════════════════════════════════════════════
   chatbot.js — Frontend conectado al backend real de ALDIMI 2.0

   Antes este archivo simulaba todo (PACIENTES_DB, OCR_SIMULADO).
   Ahora habla con la API real:
     POST /chat               -> chatbot.py
     POST /ocr/procesar       -> ocr.py (vía main.py)
     POST /pacientes/guardar  -> main.py (guarda en aldimi_pacientes.json)
     GET  /pacientes          -> main.py (para el contador del dashboard)

   Si tu backend corre en otra URL/puerto, cambia API_BASE.
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = 'http://127.0.0.1:8000';

document.addEventListener('DOMContentLoaded', () => {
  cargarUsuario();
  mostrarFecha();
  mostrarSeccion('inicio');
  mostrarEstadoOCR('vacio');
  inyectarCampoCiuOCR();
  actualizarContadorPacientes();
});


/* ── Sesión ── */
function cargarUsuario() {
  const raw = localStorage.getItem('aldimi_usuario');
  const usuario = raw ? JSON.parse(raw) : {
    nombre: 'Administrador',
    rol:    'admin',
    email:  'admin@aldimi.org',
  };

  const saludo = document.getElementById('saludo-usuario');
  if (saludo) saludo.textContent = `Bienvenido, ${usuario.nombre.split(' ')[0]}`;

  const elNombre = document.getElementById('usuario-nombre');
  const elRol    = document.getElementById('usuario-rol');
  if (elNombre) elNombre.textContent = usuario.nombre;
  if (elRol)    elRol.textContent    = usuario.rol;

  const elAvatar = document.getElementById('usuario-avatar');
  if (elAvatar) {
    const partes    = usuario.nombre.trim().split(' ');
    const iniciales = (partes[0][0] + (partes[1] ? partes[1][0] : '')).toUpperCase();
    elAvatar.textContent = iniciales;
  }
}

function cerrarSesion() {
  localStorage.removeItem('aldimi_usuario');
  window.location.href = 'index.html';
  alert('Sesión cerrada. Redirigiendo al login...');
}

function mostrarFecha() {
  const el = document.getElementById('fecha-hoy');
  if (!el) return;
  const hoy      = new Date();
  const opciones = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  el.textContent = hoy.toLocaleDateString('es-PE', opciones);
}

function mostrarSeccion(nombre) {
  document.querySelectorAll('.seccion').forEach(s => s.classList.remove('activa'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('activo'));

  const seccion = document.getElementById('seccion-' + nombre);
  if (seccion) seccion.classList.add('activa');

  const btn = document.querySelector(`.nav-btn[data-seccion="${nombre}"]`);
  if (btn) btn.classList.add('activo');
}

async function actualizarContadorPacientes() {
  const stat = document.getElementById('stat-pacientes');
  if (!stat) return;
  try {
    const res  = await fetch(`${API_BASE}/pacientes`);
    if (!res.ok) return;
    const data = await res.json();
    stat.textContent = data.total ?? 0;
  } catch (e) {
    // Backend no disponible todavía: dejamos el valor que tenía el HTML.
  }
}


/* ═══════════════════════════════════════════════════════════════
   CHATBOT
   ═══════════════════════════════════════════════════════════════ */

/* Estado conversacional — SOLO controla qué se hace con el
   PRÓXIMO mensaje del usuario. El backend no guarda estado entre
   mensajes (es stateless), así que esto vive aquí en el frontend. */
let modoConversacion = 'idle'; // 'idle' | 'esperando_ciu_registro' | 'esperando_ciu_expediente'

/* CIU "activo" de la sesión: se rellena cuando el usuario lo da en el
   chat para un registro, y se usa para precargar el campo CIU del
   panel OCR sin que tenga que volver a escribirlo. */
let ciuActivo = null;

/* Validación laxa de CIU: 8 dígitos (Perú) o 1-2 letras + 5-7 dígitos (USA/otros). */
function esCiuValido(texto) {
  const t = texto.trim().toUpperCase();
  return /^\d{8}$/.test(t) || /^[A-Z]{1,2}\d{5,7}$/.test(t);
}

function enviarMensaje() {
  const input   = document.getElementById('chat-input');
  const mensaje = input.value.trim();
  if (!mensaje) return;

  agregarMensaje(mensaje, 'usuario');
  input.value = '';
  input.disabled = true;
  document.getElementById('btn-enviar-chat').disabled = true;

  const typingId = mostrarTyping();

  procesarMensajeUsuario(mensaje).finally(() => {
    quitarTyping(typingId);
    input.disabled = false;
    document.getElementById('btn-enviar-chat').disabled = false;
    input.focus();
  });
}

async function procesarMensajeUsuario(mensaje) {
  // ── Paso conversacional: esperando CIU para REGISTRO ──
  if (modoConversacion === 'esperando_ciu_registro') {
    if (!esCiuValido(mensaje)) {
      agregarMensaje(
        'Ese CIU/DNI no parece válido. Formato Perú: 8 dígitos (ej: 42951703). ' +
        'Formato USA: letra + 5-7 dígitos (ej: W839927). Inténtalo de nuevo.',
        'bot'
      );
      return;
    }
    ciuActivo = mensaje.trim().toUpperCase();
    modoConversacion = 'idle';
    inyectarCampoCiuOCR();
    precargarCiuEnOCR(ciuActivo);
    agregarMensaje(
      `Listo, CIU ${ciuActivo} asociado al registro. Ahora ve a "Leer Documento" ` +
      `y sube la imagen del DNI. El campo CIU ya vendrá con este valor, pero puedes corregirlo si hace falta.`,
      'bot'
    );
    return;
  }

  // ── Paso conversacional: esperando CIU para EXPEDIENTE ──
  if (modoConversacion === 'esperando_ciu_expediente') {
    if (!esCiuValido(mensaje)) {
      agregarMensaje('Ese CIU no parece válido. Intenta de nuevo (ej: 42951703 o W839927).', 'bot');
      return;
    }
    modoConversacion = 'idle';
    await consultarChat('ver expediente', mensaje.trim().toUpperCase());
    return;
  }

  // ── Mensaje normal: se lo pasamos tal cual al backend ──
  await consultarChat(mensaje, null);
}

async function consultarChat(mensaje, ciu) {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ mensaje, ciu }),
    });

    if (!res.ok) {
      const detalle = await res.json().catch(() => ({}));
      agregarMensaje(`⚠️ El servidor respondió con un error: ${detalle.detail || res.status}`, 'bot');
      return;
    }

    const data = await res.json();
    agregarMensaje(data.respuesta, 'bot');

    if (data.accion === 'pedir_ciu_registro') {
      modoConversacion = 'esperando_ciu_registro';
    } else if (data.accion === 'pedir_ciu_expediente') {
      modoConversacion = 'esperando_ciu_expediente';
    }
  } catch (e) {
    agregarMensaje(
      `⚠️ No pude conectarme con el servidor (${API_BASE}). ` +
      `Verifica que el backend esté corriendo (uvicorn main:app --reload --port 8000).`,
      'bot'
    );
  }
}

/* ── Agregar burbuja al chat ── */
function agregarMensaje(texto, tipo) {
  const contenedor = document.getElementById('chat-mensajes');
  const raw        = localStorage.getItem('aldimi_usuario');
  const usuario    = raw ? JSON.parse(raw) : { nombre: 'Usuario' };
  const partes     = usuario.nombre.trim().split(' ');
  const iniciales  = (partes[0][0] + (partes[1] ? partes[1][0] : '')).toUpperCase();

  const div = document.createElement('div');
  div.className = `mensaje ${tipo}`;

  const avatar     = document.createElement('div');
  avatar.className = 'mensaje-avatar';
  if (tipo === 'bot') {
    avatar.innerHTML = '<img src="img/eva_chtb.jpg" alt="ALDIMI bot" />';
  } else {
    avatar.textContent = iniciales;
  }

  const burbuja     = document.createElement('div');
  burbuja.className = 'mensaje-burbuja';

  const html = String(texto)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .split('\n')
    .map(linea => {
      if (linea.startsWith('• ') || linea.startsWith('   • ')) return `<li>${linea.replace(/^\s*•\s*/, '')}</li>`;
      if (linea === '──────────────────') return `<hr style="border:none;border-top:1px solid rgba(0,0,0,0.1);margin:6px 0">`;
      return linea ? `<p>${linea}</p>` : '';
    })
    .join('');

  burbuja.innerHTML = html.replace(/(<li>.*?<\/li>)+/gs, match => `<ul>${match}</ul>`);

  div.appendChild(avatar);
  div.appendChild(burbuja);
  contenedor.appendChild(div);
  contenedor.scrollTop = contenedor.scrollHeight;
}

/* ── Typing indicator ── */
function mostrarTyping() {
  const contenedor = document.getElementById('chat-mensajes');
  const id         = 'typing-' + Date.now();

  const div      = document.createElement('div');
  div.className  = 'mensaje bot mensaje-typing';
  div.id         = id;

  const avatar      = document.createElement('div');
  avatar.className  = 'mensaje-avatar';
  avatar.innerHTML  = '<img src="img/eva_chtb.jpg" alt="ALDIMI bot" />';

  const burbuja      = document.createElement('div');
  burbuja.className  = 'mensaje-burbuja';
  burbuja.innerHTML  = `
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  `;

  div.appendChild(avatar);
  div.appendChild(burbuja);
  contenedor.appendChild(div);
  contenedor.scrollTop = contenedor.scrollHeight;

  return id;
}

function quitarTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/* ── Sugerencias rápidas ── */
function enviarSugerencia(btn) {
  const input = document.getElementById('chat-input');
  input.value = btn.textContent;
  enviarMensaje();
}

/* ── Limpiar chat ── */
function limpiarChat() {
  const contenedor = document.getElementById('chat-mensajes');
  const bienvenida = document.getElementById('mensaje-bienvenida');
  contenedor.innerHTML = '';
  if (bienvenida) contenedor.appendChild(bienvenida);

  // Reseteamos el "paso pendiente" pero NO el ciuActivo: si el usuario
  // ya dio un CIU para registrar y limpia el chat, no queremos que
  // pierda el campo precargado en el panel OCR.
  modoConversacion = 'idle';
}


/* ═══════════════════════════════════════════════════════════════
   OCR — "Leer Documento"
   ═══════════════════════════════════════════════════════════════ */

let archivoActual = null;
let ultimoResultadoOCR = null; // último JSON devuelto por /ocr/procesar

/* Crea el campo "CIU del paciente" arriba del botón "Extraer datos".
   No estaba en el HTML original, así que lo inyectamos una sola vez. */
function inyectarCampoCiuOCR() {
  if (document.getElementById('input-ciu-paciente')) return; // ya existe

  const panel = document.getElementById('ocr-panel-subir');
  const btnProcesar = document.getElementById('btn-procesar-ocr');
  if (!panel || !btnProcesar) return;

  const contenedor = document.createElement('div');
  contenedor.className = 'ocr-campo';
  contenedor.id = 'ocr-ciu-contenedor';
  contenedor.style.marginTop = '12px';

  const label = document.createElement('label');
  label.textContent = 'CIU del paciente (obligatorio para guardar)';
  label.setAttribute('for', 'input-ciu-paciente');

  const input = document.createElement('input');
  input.type = 'text';
  input.id = 'input-ciu-paciente';
  input.placeholder = 'Ej: 42951703 o W839927';

  contenedor.appendChild(label);
  contenedor.appendChild(input);
  panel.insertBefore(contenedor, btnProcesar);
}

function precargarCiuEnOCR(ciu) {
  const input = document.getElementById('input-ciu-paciente');
  if (input && !input.value) input.value = ciu;
}

function cargarImagen(evento) {
  const archivo = evento.target.files[0];
  if (!archivo) return;
  procesarArchivo(archivo);
}

function soltarArchivo(evento) {
  evento.preventDefault();
  document.getElementById('zona-subir').classList.remove('arrastrando');
  const archivo = evento.dataTransfer.files[0];
  if (!archivo) return;

  const tiposPermitidos = ['image/jpeg', 'image/png'];
  if (!tiposPermitidos.includes(archivo.type)) {
    alert('Solo se permiten imágenes JPG o PNG.');
    return;
  }
  if (archivo.size > 5 * 1024 * 1024) {
    alert('La imagen supera los 5MB permitidos.');
    return;
  }
  procesarArchivo(archivo);
}

function procesarArchivo(archivo) {
  archivoActual = archivo;
  ultimoResultadoOCR = null;

  document.getElementById('preview-nombre-archivo').textContent = archivo.name;

  const reader  = new FileReader();
  reader.onload = (e) => {
    const img = document.getElementById('preview-imagen');
    img.src   = e.target.result;
    document.getElementById('preview-contenedor').classList.add('visible');
  };
  reader.readAsDataURL(archivo);

  // El tipo real lo decide el backend (clasificar_documento en ocr.py),
  // no adivinamos nada por el nombre del archivo.
  document.getElementById('tipo-documento-contenedor').classList.remove('visible');
  document.getElementById('btn-procesar-ocr').classList.add('visible');
  document.getElementById('btn-limpiar-ocr').classList.add('visible');

  mostrarEstadoOCR('vacio');
}

async function procesarOCR() {
  if (!archivoActual) return;

  const btnProcesar = document.getElementById('btn-procesar-ocr');
  btnProcesar.textContent = 'Procesando...';
  btnProcesar.disabled = true;
  mostrarEstadoOCR('procesando');

  const formData = new FormData();
  formData.append('archivo', archivoActual);

  try {
    const res = await fetch(`${API_BASE}/ocr/procesar`, { method: 'POST', body: formData });

    if (!res.ok) {
      const detalle = await res.json().catch(() => ({}));
      mostrarErrorOCR(detalle.detail || `Error del servidor (${res.status}).`);
      return;
    }

    const data = await res.json();
    ultimoResultadoOCR = data;
    mostrarResultadoOCR(data);

  } catch (e) {
    mostrarErrorOCR(`No pude conectarme con el servidor (${API_BASE}). ¿Está corriendo el backend?`);
  } finally {
    btnProcesar.textContent = 'Extraer datos';
    btnProcesar.disabled = false;
  }
}

function mostrarErrorOCR(mensaje) {
  document.getElementById('ocr-error-texto').textContent = mensaje;
  mostrarEstadoOCR('error');
}

function mostrarResultadoOCR(data) {
  const badge = document.getElementById('tipo-documento-badge');
  const etiquetas = {
    DNI_PERU:   'DNI Perú',
    DNI_USA:    'Licencia / ID USA',
    LAB_REPORT: 'Informe de laboratorio',
    UNKNOWN:    'No identificado',
  };
  badge.textContent = etiquetas[data.tipo_documento] || data.tipo_documento;
  document.getElementById('tipo-documento-contenedor').classList.add('visible');

  const contenedorCampos = document.getElementById('ocr-campos');
  contenedorCampos.innerHTML = '';
  contenedorCampos.dataset.tipoDocumento = data.tipo_documento;

  if (data.tipo_documento === 'DNI_PERU' || data.tipo_documento === 'DNI_USA') {
    renderCamposDNI(contenedorCampos, data.campos);
    if (data.campos && data.campos.ciu) precargarCiuEnOCR(data.campos.ciu);

  } else if (data.tipo_documento === 'LAB_REPORT') {
    renderCamposLAB(contenedorCampos, data.campos);
    if (data.campos && data.campos.ciu) precargarCiuEnOCR(data.campos.ciu);

  } else {
    renderTipoDesconocido(contenedorCampos, data);
  }

  const obs = document.getElementById('ocr-observacion-texto');
  if (data.tipo_documento === 'UNKNOWN') {
    obs.textContent = data.advertencia ||
      'No se pudo determinar si es un DNI o un informe de laboratorio. Selecciona el tipo manualmente y completa los campos.';
  } else {
    obs.textContent = '✓ Documento identificado. Revisa los datos y corrígelos si el escaneo salió mal antes de guardar.';
  }
  document.getElementById('ocr-observacion').classList.add('visible');

  mostrarEstadoOCR('resultado');
}

function crearCampoTexto(label, valor, name) {
  const div = document.createElement('div');
  div.className = 'ocr-campo';

  const lbl = document.createElement('label');
  lbl.textContent = label;

  const input = document.createElement('input');
  input.type = 'text';
  input.value = valor && valor !== 'NO_DETECTADO' ? valor : '';
  input.placeholder = valor === 'NO_DETECTADO' ? 'No se detectó — complétalo manualmente' : '';
  input.dataset.campo = name;
  input.readOnly = true;

  div.appendChild(lbl);
  div.appendChild(input);
  return div;
}

function renderCamposDNI(contenedor, campos) {
  campos = campos || {};
  const titulo = document.createElement('p');
  titulo.className = 'ocr-seccion-titulo';
  titulo.textContent = 'Datos del documento';
  contenedor.appendChild(titulo);

  contenedor.appendChild(crearCampoTexto('Nombres', campos.nombres, 'nombres'));
  contenedor.appendChild(crearCampoTexto('Apellidos', campos.apellidos, 'apellidos'));
  contenedor.appendChild(crearCampoTexto('Fecha de nacimiento', campos.fecha_nacimiento, 'fecha_nacimiento'));
}

function renderCamposLAB(contenedor, campos) {
  campos = campos || {};
  const pruebas = campos.pruebas || [];

  const titulo = document.createElement('p');
  titulo.className = 'ocr-seccion-titulo';
  titulo.textContent = `Pruebas detectadas (${pruebas.length})`;
  contenedor.appendChild(titulo);

  if (pruebas.length === 0) {
    const vacio = document.createElement('p');
    vacio.textContent = 'No se detectaron pruebas legibles. Revisa el escaneo o complétalas manualmente más adelante.';
    contenedor.appendChild(vacio);
    return;
  }

  pruebas.forEach((p, idx) => {
    const div = document.createElement('div');
    div.className = 'ocr-campo ocr-resultado' + (p.flag ? ' ocr-resultado--alt' : '');
    div.dataset.pruebaIdx = idx;

    const fila = document.createElement('div');
    fila.className = 'ocr-resultado-fila';

    const nombreInput = document.createElement('input');
    nombreInput.type = 'text';
    nombreInput.value = p.nombre || '';
    nombreInput.dataset.campo = 'nombre';
    nombreInput.readOnly = true;
    nombreInput.style.fontWeight = '600';

    const valorInput = document.createElement('input');
    valorInput.type = 'text';
    valorInput.value = p.valor ?? '';
    valorInput.dataset.campo = 'valor';
    valorInput.readOnly = true;

    const unidadInput = document.createElement('input');
    unidadInput.type = 'text';
    unidadInput.value = p.unidad || '';
    unidadInput.placeholder = 'unidad';
    unidadInput.dataset.campo = 'unidad';
    unidadInput.readOnly = true;
    unidadInput.style.maxWidth = '90px';

    const flagSelect = document.createElement('select');
    flagSelect.dataset.campo = 'flag';
    flagSelect.disabled = true;
    ['', 'H', 'L'].forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v === '' ? 'Normal' : (v === 'H' ? 'Alto [H]' : 'Bajo [L]');
      if (v === (p.flag || '')) opt.selected = true;
      flagSelect.appendChild(opt);
    });

    fila.appendChild(nombreInput);
    fila.appendChild(valorInput);
    fila.appendChild(unidadInput);
    fila.appendChild(flagSelect);
    div.appendChild(fila);

    const refInput = document.createElement('input');
    refInput.type = 'text';
    refInput.value = p.referencia || '';
    refInput.placeholder = 'Rango de referencia';
    refInput.dataset.campo = 'referencia';
    refInput.readOnly = true;
    refInput.className = 'ocr-resultado-ref';
    refInput.style.width = '100%';
    refInput.style.marginTop = '4px';
    div.appendChild(refInput);

    contenedor.appendChild(div);
  });
}

function renderTipoDesconocido(contenedor, data) {
  const aviso = document.createElement('p');
  aviso.textContent = 'No se pudo clasificar automáticamente. Elige el tipo de documento:';
  contenedor.appendChild(aviso);

  const selector = document.createElement('select');
  selector.id = 'selector-tipo-manual';
  [['', 'Selecciona...'], ['DNI', 'DNI / documento de identidad'], ['LAB', 'Informe de laboratorio']]
    .forEach(([val, txt]) => {
      const opt = document.createElement('option');
      opt.value = val;
      opt.textContent = txt;
      selector.appendChild(opt);
    });
  selector.onchange = () => {
    const restoCampos = contenedor.querySelectorAll('.ocr-campo, .ocr-seccion-titulo');
    restoCampos.forEach(el => el.remove());
    if (selector.value === 'DNI') {
      renderCamposDNI(contenedor, {});
    } else if (selector.value === 'LAB') {
      renderCamposLAB(contenedor, { pruebas: [] });
    }
    contenedor.dataset.tipoDocumento = selector.value === 'DNI' ? 'DNI_PERU' : (selector.value === 'LAB' ? 'LAB_REPORT' : 'UNKNOWN');
  };
  contenedor.appendChild(selector);

  const textoCrudo = document.createElement('textarea');
  textoCrudo.readOnly = true;
  textoCrudo.value = data.texto_crudo || '';
  textoCrudo.style.width = '100%';
  textoCrudo.style.minHeight = '120px';
  textoCrudo.style.marginTop = '10px';
  contenedor.appendChild(textoCrudo);
}

function habilitarEdicion() {
  const campos = document.querySelectorAll('#ocr-campos input, #ocr-campos select, #ocr-campos textarea');
  campos.forEach(el => {
    el.readOnly = false;
    el.disabled = false;
  });
  const btn = document.getElementById('btn-editar-ocr');
  btn.textContent = 'Editando...';
  btn.disabled = true;
}

async function guardarDatos() {
  const ciuInput = document.getElementById('input-ciu-paciente');
  const ciu = ciuInput ? ciuInput.value.trim().toUpperCase() : '';

  if (!esCiuValido(ciu)) {
    alert('Ingresa un CIU/DNI válido antes de guardar (8 dígitos o letra + 5-7 dígitos).');
    if (ciuInput) ciuInput.focus();
    return;
  }

  const contenedor = document.getElementById('ocr-campos');
  const tipoDoc = contenedor.dataset.tipoDocumento || 'UNKNOWN';

  let tipoDocumento, campos;

  if (tipoDoc.startsWith('DNI')) {
    tipoDocumento = 'DNI';
    campos = {
      nombres: contenedor.querySelector('input[data-campo="nombres"]')?.value.trim() || 'NO_DETECTADO',
      apellidos: contenedor.querySelector('input[data-campo="apellidos"]')?.value.trim() || 'NO_DETECTADO',
      fecha_nacimiento: contenedor.querySelector('input[data-campo="fecha_nacimiento"]')?.value.trim() || 'NO_DETECTADO',
    };

  } else if (tipoDoc === 'LAB_REPORT') {
    tipoDocumento = 'LAB';
    const filas = contenedor.querySelectorAll('[data-prueba-idx]');
    const pruebas = [];
    const alertas = [];

    filas.forEach(fila => {
      const nombre = fila.querySelector('[data-campo="nombre"]')?.value.trim();
      const valorTxt = fila.querySelector('[data-campo="valor"]')?.value.trim();
      const unidad = fila.querySelector('[data-campo="unidad"]')?.value.trim() || '';
      const referencia = fila.querySelector('[data-campo="referencia"]')?.value.trim() || '';
      const flag = fila.querySelector('[data-campo="flag"]')?.value || '';
      if (!nombre || !valorTxt) return;

      const valor = parseFloat(valorTxt.replace(',', '.'));
      const prueba = { nombre, valor: isNaN(valor) ? valorTxt : valor, unidad, referencia, flag };
      pruebas.push(prueba);

      if (flag === 'H' || flag === 'L') {
        alertas.push({
          prueba: nombre,
          valor: prueba.valor,
          tipo: flag === 'H' ? 'ALTO [H]' : 'BAJO [L]',
          unidad,
          referencia,
        });
      }
    });

    campos = { pruebas, alertas_detectadas: alertas };

  } else {
    alert('Selecciona primero el tipo de documento (DNI o Laboratorio) antes de guardar.');
    return;
  }

  const btnGuardar = document.getElementById('btn-guardar-ocr');
  btnGuardar.disabled = true;
  btnGuardar.textContent = 'Guardando...';

  try {
    const res = await fetch(`${API_BASE}/pacientes/guardar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ciu, tipo_documento: tipoDocumento, campos }),
    });

    if (!res.ok) {
      const detalle = await res.json().catch(() => ({}));
      alert(`No se pudo guardar: ${detalle.detail || res.status}`);
      return;
    }

    await actualizarContadorPacientes();

    const siguientePaso = tipoDocumento === 'DNI'
      ? '\n\nSi ya tienes el informe de laboratorio de este paciente, súbelo ahora con el mismo CIU.'
      : '';
    alert(`✓ Datos guardados correctamente para CIU ${ciu}.${siguientePaso}`);

    limpiarOCR();
    // Mantenemos el CIU precargado por si el usuario sigue subiendo
    // documentos del mismo paciente (ej. DNI y luego el informe de lab).
    const ciuInputNuevo = document.getElementById('input-ciu-paciente');
    if (ciuInputNuevo) ciuInputNuevo.value = ciu;

  } catch (e) {
    alert(`No pude conectarme con el servidor (${API_BASE}).`);
  } finally {
    btnGuardar.disabled = false;
    btnGuardar.textContent = 'Guardar en sistema';
  }
}

function limpiarOCR() {
  archivoActual = null;
  ultimoResultadoOCR = null;

  const inputImg = document.getElementById('input-imagen');
  if (inputImg) inputImg.value = '';

  document.getElementById('preview-contenedor').classList.remove('visible');
  document.getElementById('preview-imagen').src = '';
  document.getElementById('preview-nombre-archivo').textContent = '';

  document.getElementById('tipo-documento-contenedor').classList.remove('visible');
  document.getElementById('tipo-documento-badge').textContent = '';

  document.getElementById('btn-procesar-ocr').classList.remove('visible');
  document.getElementById('btn-limpiar-ocr').classList.remove('visible');

  const btnEditar = document.getElementById('btn-editar-ocr');
  btnEditar.textContent = 'Editar datos';
  btnEditar.disabled = false;

  document.getElementById('ocr-observacion').classList.remove('visible');
  document.getElementById('ocr-campos').innerHTML = '';

  mostrarEstadoOCR('vacio');
}

function mostrarEstadoOCR(estado) {
  const estados = ['vacio', 'procesando', 'resultado', 'error'];
  estados.forEach(e => {
    const el = document.getElementById('ocr-estado-' + e);
    if (el) el.classList.toggle('visible', e === estado);
  });
}