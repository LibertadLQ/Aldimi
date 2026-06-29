// ── URL de la API ─────────────────────────────────────────────────────────────
const API_URL = 'https://aldimi-api.onrender.com';

document.addEventListener('DOMContentLoaded', () => {
  cargarUsuario();
  mostrarFecha();
  mostrarSeccion('inicio');
  mostrarEstadoOCR('vacio');
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
  const hoy     = new Date();
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

// ══════════════════════════════════════════════════════════════════════════════
// CHATBOT — conectado a la API real
// ══════════════════════════════════════════════════════════════════════════════

let estadoBot      = 'idle';
let pacienteActual = null;

function enviarMensaje() {
  const input   = document.getElementById('chat-input');
  const mensaje = input.value.trim();
  if (!mensaje) return;

  agregarMensaje(mensaje, 'usuario');
  input.value = '';

  input.disabled = true;
  document.getElementById('btn-enviar-chat').disabled = true;

  const typingId = mostrarTyping();

  // Llamada real a la API
  fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mensaje }),
  })
    .then(r => r.json())
    .then(data => {
      quitarTyping(typingId);
      agregarMensaje(data.respuesta, 'bot');

      // Actualizar contador de consultas
      const statConsultas = document.getElementById('stat-consultas');
      if (statConsultas) statConsultas.textContent = parseInt(statConsultas.textContent || 0) + 1;
    })
    .catch(() => {
      quitarTyping(typingId);
      agregarMensaje(
        'Lo siento, no pude conectarme al servidor. Por favor intenta en unos segundos.',
        'bot'
      );
    })
    .finally(() => {
      input.disabled = false;
      document.getElementById('btn-enviar-chat').disabled = false;
      input.focus();
    });
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

  const html = texto
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .split('\n')
    .map(linea => {
      if (linea.startsWith('• ')) return `<li>${linea.slice(2)}</li>`;
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

  const div     = document.createElement('div');
  div.className = 'mensaje bot mensaje-typing';
  div.id        = id;

  const avatar     = document.createElement('div');
  avatar.className = 'mensaje-avatar';
  avatar.innerHTML = '<img src="img/eva_chtb.jpg" alt="ALDIMI bot" />';

  const burbuja     = document.createElement('div');
  burbuja.className = 'mensaje-burbuja';
  burbuja.innerHTML = `
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
  estadoBot      = 'idle';
  pacienteActual = null;
}

// ══════════════════════════════════════════════════════════════════════════════
// OCR — conectado a la API real
// ══════════════════════════════════════════════════════════════════════════════

let archivoActual = null;
let ultimoResultadoOCR = null;   // datos crudos devueltos por la API (no lo que se ve en pantalla)
let ultimoTipoOCR       = null;  // 'dni' | 'lab'

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

  if (!['image/jpeg', 'image/png'].includes(archivo.type)) {
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

  document.getElementById('preview-nombre-archivo').textContent = archivo.name;

  const reader  = new FileReader();
  reader.onload = (e) => {
    const img = document.getElementById('preview-imagen');
    img.src   = e.target.result;
    document.getElementById('preview-contenedor').classList.add('visible');
  };
  reader.readAsDataURL(archivo);

  const nombre = archivo.name.toLowerCase();
  let tipo = 'Documento';
  if (nombre.includes('dni') || nombre.includes('identidad')) tipo = 'DNI';
  else if (nombre.includes('lab') || nombre.includes('medic') || nombre.includes('receta')) tipo = 'Documento Médico';

  document.getElementById('tipo-documento-badge').textContent = tipo;
  document.getElementById('tipo-documento-contenedor').classList.add('visible');
  document.getElementById('btn-procesar-ocr').classList.add('visible');
  document.getElementById('btn-limpiar-ocr').classList.add('visible');

  mostrarEstadoOCR('vacio');
}

/* ── Procesar OCR — llama a la API real ── */
async function procesarOCR() {
  if (!archivoActual) return;

  const btnProcesar      = document.getElementById('btn-procesar-ocr');
  btnProcesar.textContent = 'Procesando...';
  btnProcesar.disabled    = true;
  mostrarEstadoOCR('procesando');

  const nombre   = archivoActual.name.toLowerCase();
  const esDNI    = nombre.includes('dni') || nombre.includes('identidad');

  // Para informes de laboratorio se necesita el CIU del paciente para asociarlo.
  // Si ya tenemos un paciente activo (por ejemplo, recién se procesó su DNI),
  // se usa ese CIU sin volver a preguntar.
  let ciuParaLab = '';
  if (!esDNI) {
    ciuParaLab = pacienteActual || prompt('Ingrese el CIU del paciente para asociar este informe:', '') || '';
    if (!ciuParaLab) {
      btnProcesar.textContent = 'Extraer datos';
      btnProcesar.disabled    = false;
      mostrarEstadoOCR('vacio');
      return;
    }
  }

  const endpoint = esDNI ? `${API_URL}/ocr/dni` : `${API_URL}/ocr/lab`;

  const formData = new FormData();
  formData.append('imagen', archivoActual);
  if (!esDNI) formData.append('ciu', ciuParaLab);

  try {
    const resp = await fetch(endpoint, { method: 'POST', body: formData });
    const data = await resp.json();

    btnProcesar.textContent = 'Extraer datos';
    btnProcesar.disabled    = false;

    if (!data.ok) {
      document.getElementById('ocr-error-texto').textContent =
        data.mensaje || 'No se pudo procesar el documento.';
      mostrarEstadoOCR('error');
      return;
    }

    // Guardar los datos crudos (no solo lo que se muestra) para poder
    // enviarlos tal cual a /registro cuando el usuario presione "Guardar".
    ultimoResultadoOCR = data;
    ultimoTipoOCR      = esDNI ? 'dni' : 'lab';
    if (esDNI && data.ciu) pacienteActual = data.ciu;
    if (!esDNI) pacienteActual = ciuParaLab;

    // Mostrar resultados según tipo
    if (esDNI) {
      mostrarResultadoOCR({
        tipo: 'DNI',
        secciones: [{
          titulo: 'Datos del documento',
          campos: [
            { label: 'Nombres',    valor: data.nombres   || 'No detectado' },
            { label: 'Apellidos',  valor: data.apellidos || 'No detectado' },
            { label: 'CIU / DNI',  valor: data.ciu       || 'No detectado' },
            { label: 'Fecha Nac.', valor: data.fecha_nacimiento || 'No detectado' },
            { label: 'Tipo',       valor: data.tipo_dni  || 'No detectado' },
          ],
        }],
        observacion: '✓ Documento procesado con OCR. Verifique los datos antes de guardar.',
      });
    } else {
      // Informe de laboratorio
      const campos = (data.pruebas || []).map(p => ({
        label: p.nombre,
        valor: `${p.valor} ${p.unidad || ''}`.trim(),
        ref:   p.referencia || '—',
        ok:    !p.flag || p.flag === '',
        nota:  p.flag === 'H' ? 'Elevado' : p.flag === 'L' ? 'Bajo' : '',
      }));

      mostrarResultadoOCR({
        tipo: 'Reporte de Laboratorio',
        secciones: [
          {
            titulo: 'Resultados',
            esResultados: true,
            campos: campos.length > 0 ? campos : [
              { label: 'Resultado', valor: data.resumen || 'Sin datos numéricos detectados', ref: '—', ok: true }
            ],
          },
        ],
        observacion: data.alertas && data.alertas.length > 0
          ? `⚠️ Se detectaron ${data.alertas.length} valor(es) fuera de rango. Consulte con el médico.`
          : '✓ Informe procesado. Todos los valores dentro del rango normal.',
      });
    }

    // Actualizar contador
    const statDocs = document.getElementById('stat-documentos');
    if (statDocs) statDocs.textContent = parseInt(statDocs.textContent || 0) + 1;

  } catch (err) {
    btnProcesar.textContent = 'Extraer datos';
    btnProcesar.disabled    = false;
    document.getElementById('ocr-error-texto').textContent =
      'Error de conexión con el servidor. Intenta de nuevo.';
    mostrarEstadoOCR('error');
  }
}

function mostrarResultadoOCR(datos) {
  const contenedorCampos     = document.getElementById('ocr-campos');
  contenedorCampos.innerHTML = '';

  datos.secciones.forEach(seccion => {
    const titulo       = document.createElement('p');
    titulo.className   = 'ocr-seccion-titulo';
    titulo.textContent = seccion.titulo;
    contenedorCampos.appendChild(titulo);

    if (seccion.esResultados) {
      seccion.campos.forEach(campo => {
        const div     = document.createElement('div');
        div.className = 'ocr-campo ocr-resultado' + (campo.ok ? '' : ' ocr-resultado--alt');

        const fila     = document.createElement('div');
        fila.className = 'ocr-resultado-fila';

        const label       = document.createElement('label');
        label.textContent = campo.label;

        const input    = document.createElement('input');
        input.type     = 'text';
        input.value    = campo.valor;
        input.readOnly = true;

        const badge       = document.createElement('span');
        badge.className   = 'ocr-resultado-badge ' + (campo.ok ? 'badge-ok' : 'badge-alt');
        badge.textContent = campo.ok ? 'Normal' : (campo.nota || 'Fuera de rango');

        fila.appendChild(label);
        fila.appendChild(input);
        fila.appendChild(badge);
        div.appendChild(fila);

        const ref       = document.createElement('span');
        ref.className   = 'ocr-resultado-ref';
        ref.textContent = 'Ref: ' + campo.ref;
        div.appendChild(ref);

        contenedorCampos.appendChild(div);
      });
    } else {
      seccion.campos.forEach(campo => {
        const div     = document.createElement('div');
        div.className = 'ocr-campo';

        const label       = document.createElement('label');
        label.textContent = campo.label;

        const input    = document.createElement('input');
        input.type     = 'text';
        input.value    = campo.valor;
        input.readOnly = true;

        div.appendChild(label);
        div.appendChild(input);
        contenedorCampos.appendChild(div);
      });
    }
  });

  const obsTxt       = document.getElementById('ocr-observacion-texto');
  obsTxt.textContent = datos.observacion;
  document.getElementById('ocr-observacion').classList.add('visible');

  mostrarEstadoOCR('resultado');
}

function habilitarEdicion() {
  const inputs = document.querySelectorAll('#ocr-campos input');
  inputs.forEach(inp => {
    inp.readOnly = false;
    inp.focus();
  });
  document.getElementById('btn-editar-ocr').textContent = 'Editando...';
  document.getElementById('btn-editar-ocr').disabled    = true;
}

async function guardarDatos() {
  if (!ultimoResultadoOCR || !ultimoTipoOCR) {
    alert('No hay datos para guardar. Procese un documento primero.');
    return;
  }

  // Si el usuario habilitó edición manual, se toman los valores actuales
  // de los inputs (por si corrigió algo a mano) en vez de los datos crudos.
  const inputsEditados = {};
  document.querySelectorAll('#ocr-campos .ocr-campo').forEach(campo => {
    const label = campo.querySelector('label');
    const input = campo.querySelector('input');
    if (label && input) inputsEditados[label.textContent] = input.value;
  });

  const btnGuardar = document.getElementById('btn-guardar-ocr');
  btnGuardar.textContent = 'Guardando...';
  btnGuardar.disabled    = true;

  let body;
  if (ultimoTipoOCR === 'dni') {
    const ciu = inputsEditados['CIU / DNI'] || ultimoResultadoOCR.ciu;
    if (!ciu) {
      alert('No se detectó un CIU/DNI válido. Verifique el documento o edítelo manualmente.');
      btnGuardar.textContent = 'Guardar en sistema';
      btnGuardar.disabled    = false;
      return;
    }
    body = {
      ciu: ciu,
      dni_data: {
        ciu:              ciu,
        tipo_dni:         inputsEditados['Tipo'] || ultimoResultadoOCR.tipo_dni,
        nombres:          inputsEditados['Nombres']    || ultimoResultadoOCR.nombres,
        apellidos:        inputsEditados['Apellidos']  || ultimoResultadoOCR.apellidos,
        fecha_nacimiento: inputsEditados['Fecha Nac.'] || ultimoResultadoOCR.fecha_nacimiento,
      },
    };
  } else {
    if (!pacienteActual) {
      alert('No hay un CIU de paciente asociado a este informe.');
      btnGuardar.textContent = 'Guardar en sistema';
      btnGuardar.disabled    = false;
      return;
    }
    body = {
      ciu: pacienteActual,
      lab_data: {
        tipo_informe:        ultimoResultadoOCR.tipo_informe || 'LAB_REPORT',
        tipo_analisis:       ultimoResultadoOCR.tipo_analisis || 'Análisis de Laboratorio',
        pruebas:             ultimoResultadoOCR.pruebas || [],
        alertas_detectadas:  ultimoResultadoOCR.alertas || [],
      },
    };
  }

  try {
    const resp = await fetch(`${API_URL}/registro`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();

    btnGuardar.textContent = 'Guardar en sistema';
    btnGuardar.disabled    = false;

    if (!resp.ok || !data.ok) {
      alert('No se pudo guardar: ' + (data.detail || data.mensaje || 'Error desconocido'));
      return;
    }

    const statDocs = document.getElementById('stat-documentos');
    if (statDocs) statDocs.textContent = parseInt(statDocs.textContent || 0) + 1;
    const statPacientes = document.getElementById('stat-pacientes');
    if (statPacientes) statPacientes.textContent = parseInt(statPacientes.textContent || 0) + 1;

    alert('✓ Datos guardados correctamente en el sistema (CIU: ' + body.ciu + ').');
    limpiarOCR();

  } catch (err) {
    btnGuardar.textContent = 'Guardar en sistema';
    btnGuardar.disabled    = false;
    alert('Error de conexión al guardar. Intenta de nuevo.');
  }
}

function limpiarOCR() {
  archivoActual      = null;
  ultimoResultadoOCR = null;
  ultimoTipoOCR      = null;

  const inputImg = document.getElementById('input-imagen');
  if (inputImg) inputImg.value = '';

  document.getElementById('preview-contenedor').classList.remove('visible');
  document.getElementById('preview-imagen').src              = '';
  document.getElementById('preview-nombre-archivo').textContent = '';

  document.getElementById('tipo-documento-contenedor').classList.remove('visible');
  document.getElementById('tipo-documento-badge').textContent   = '';

  document.getElementById('btn-procesar-ocr').classList.remove('visible');
  document.getElementById('btn-limpiar-ocr').classList.remove('visible');

  const btnEditar       = document.getElementById('btn-editar-ocr');
  btnEditar.textContent = 'Editar datos';
  btnEditar.disabled    = false;

  document.getElementById('ocr-observacion').classList.remove('visible');

  mostrarEstadoOCR('vacio');
}

function mostrarEstadoOCR(estado) {
  const estados = ['vacio', 'procesando', 'resultado', 'error'];
  estados.forEach(e => {
    const el = document.getElementById('ocr-estado-' + e);
    if (el) el.classList.toggle('visible', e === estado);
  });
}