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

//CHATBOT

/* ── Estado conversacional ── */
let estadoBot      = 'idle'; // 'idle' | 'esperando_dni' | 'esperando_lab'
let pacienteActual = null;

/* ── Base de datos simulada de pacientes ── */
const PACIENTES_DB = {
  '45678912': {
    nombre:      'Juan Carlos Pérez Mamani',
    edad:        9,
    tutor:       'María Mamani Quispe',
    diagnostico: 'Leucemia linfoblástica aguda (LLA)',
    ciclo:       'Ciclo 3 — Consolidación',
    ingreso:     '14/01/2025',
    lab: [
      { test: 'Hemoglobina',  val: '10.2 g/dL',    ref: '12–16 g/dL',          ok: false },
      { test: 'Leucocitos',   val: '3,200 /µL',     ref: '4,000–11,000 /µL',    ok: false },
      { test: 'Plaquetas',    val: '180,000 /µL',   ref: '150,000–400,000 /µL', ok: true  },
      { test: 'Creatinina',   val: '0.6 mg/dL',     ref: '0.5–1.2 mg/dL',       ok: true  },
      { test: 'TGO (AST)',    val: '38 U/L',         ref: '10–40 U/L',           ok: true  },
      { test: 'TGP (ALT)',    val: '52 U/L',         ref: '7–56 U/L',            ok: true  },
    ],
  },
  '72345678': {
    nombre:      'Lucía Quispe Torres',
    edad:        7,
    tutor:       'Roberto Quispe Condori',
    diagnostico: 'Tumor de Wilms (nefroblastoma)',
    ciclo:       'Post-cirugía — Quimioterapia adyuvante',
    ingreso:     '03/03/2025',
    lab: [
      { test: 'Hemoglobina',  val: '11.8 g/dL',    ref: '12–16 g/dL',          ok: false },
      { test: 'Leucocitos',   val: '6,100 /µL',     ref: '4,000–11,000 /µL',    ok: true  },
      { test: 'Plaquetas',    val: '220,000 /µL',   ref: '150,000–400,000 /µL', ok: true  },
      { test: 'Creatinina',   val: '0.9 mg/dL',     ref: '0.5–1.2 mg/dL',       ok: true  },
      { test: 'TGO (AST)',    val: '44 U/L',         ref: '10–40 U/L',           ok: false },
      { test: 'TGP (ALT)',    val: '30 U/L',         ref: '7–56 U/L',            ok: true  },
    ],
  },
};

/* ── Respuestas fijas para intenciones simples ── */
const RESPUESTAS_BOT = {
  HORARIO: {
    palabras: ['horario','hora','visita','apertura','cierre','atiende','abren','abierto','cuando'],
    respuesta: 'El horario de visitas del Albergue ALDIMI es:\n\n• Lunes a Sábado: 9:00 a.m. a 6:00 p.m.\n\n¿Desea información sobre algún otro servicio?',
  },
  REGISTRO: {
    palabras: ['registrar','registro','ingreso','documentos','admisión','admision','paciente','inscribir','nuevo'],
    respuesta: 'Para registrar un paciente necesitas:\n\n• DNI del paciente y del apoderado\n• Diagnóstico médico actualizado\n• Documento de pobreza (si aplica)\n\nPuedes usar el módulo "Leer Documento" para digitalizar el DNI automáticamente.',
  },
  DONACION: {
    palabras: ['donar','donación','donacion','donaciones','ropa','yape','apoyo','transferencia','cuenta','ayuda','plin'],
    respuesta: '¡Gracias por querer apoyar a ALDIMI!\n\nPuedes donar mediante:\n• Yape / Plin: 999-000-111\n• Transferencia bancaria: Cta. 123-456789\n• Donación de ropa y útiles: sede central\n\n¿Deseas más información?',
  },
  EMOCIONAL: {
    palabras: ['deprimido','ansiedad','triste','no quiero vivir','desesperado','llora','asustado','sin salida','suicidio'],
    respuesta: 'Se ha detectado una posible situación de riesgo emocional.\n\nSe registrará una alerta para el equipo de soporte psicosocial. El personal evaluará el caso a la brevedad.\n\n¿Puede indicar el ID del paciente para asociar la alerta?',
  },
};

/* ── Detectar intención simple ── */
function detectarIntencionSimple(mensaje) {
  const lower = mensaje.toLowerCase();
  let mejorIntencion = null;
  let mejorPuntaje   = 0;

  for (const [intencion, datos] of Object.entries(RESPUESTAS_BOT)) {
    const coincidencias = datos.palabras.filter(p => lower.includes(p)).length;
    const puntaje       = coincidencias / datos.palabras.length;
    if (puntaje > mejorPuntaje) {
      mejorPuntaje   = puntaje;
      mejorIntencion = intencion;
    }
  }

  if (mejorPuntaje < 0.05) return null;
  return mejorIntencion;
}

/* ── Detectar si el usuario quiere un expediente ── */
function esIntentExpediente(lower) {
  const palabras = ['expediente','reporte','historial','buscar paciente','consultar paciente','ver paciente','datos del paciente'];
  return palabras.some(p => lower.includes(p));
}

/* ── Enviar mensaje del usuario ── */
function enviarMensaje() {
  const input   = document.getElementById('chat-input');
  const mensaje = input.value.trim();
  if (!mensaje) return;

  agregarMensaje(mensaje, 'usuario');
  input.value = '';

  input.disabled = true;
  document.getElementById('btn-enviar-chat').disabled = true;

  const typingId = mostrarTyping();
  const delay    = 800 + Math.random() * 600;

  setTimeout(() => {
    quitarTyping(typingId);
    responderBot(mensaje);
    input.disabled = false;
    document.getElementById('btn-enviar-chat').disabled = false;
    input.focus();
  }, delay);
}

/* ── Lógica principal del bot ── */
function responderBot(mensaje) {
  const lower = mensaje.toLowerCase().trim();

  /* ── Estado: esperando DNI ── */
  if (estadoBot === 'esperando_dni') {
    const dni = mensaje.replace(/\s/g, '');

    if (/^\d{8}$/.test(dni) && PACIENTES_DB[dni]) {
      const p        = PACIENTES_DB[dni];
      pacienteActual = p;
      estadoBot      = 'esperando_lab';

      agregarMensaje(
        `Paciente encontrado\n\n` +
        `Nombre: ${p.nombre}\n` +
        `Edad: ${p.edad} años\n` +
        `Tutor / Apoderado: ${p.tutor}\n` +
        `Diagnóstico: ${p.diagnostico}\n` +
        `Estado de tratamiento: ${p.ciclo}\n` +
        `Fecha de ingreso: ${p.ingreso}\n\n` +
        `¿Deseas ver el reporte de laboratorio más reciente?\nResponde sí o no.`,
        'bot'
      );

    } else if (/^\d{8}$/.test(dni)) {
      agregarMensaje(
        ` No encontré ningún paciente con DNI ${dni}.\n\nVerifica el número e intenta nuevamente.`,
        'bot'
      );

    } else {
      agregarMensaje(
        `Por favor ingresa un DNI válido de 8 dígitos. Ejemplo: 45678912`,
        'bot'
      );
    }
    return;
  }

  /* ── Estado: esperando respuesta sobre laboratorio ── */
  if (estadoBot === 'esperando_lab') {

    if (/s[ií]|^si$|quiero|ver|muestra|mostrar|sí/.test(lower)) {
      estadoBot = 'idle';
      const p   = pacienteActual;

      let textoLab =
        `Reporte de laboratorio — ${p.nombre}\n` +
        `Resultados más recientes\n\n`;

      p.lab.forEach(l => {
        const icono = l.ok ? '✅' : '⚠️';
        textoLab += `${icono} ${l.test}: ${l.val}   (ref: ${l.ref})\n`;
      });

      textoLab +=
        `\n──────────────────\n` +
        `¿Deseas consultar otro expediente o necesitas algo más?`;

      agregarMensaje(textoLab, 'bot');

    } else if (/^no\b/.test(lower)) {
      estadoBot = 'idle';
      agregarMensaje(
        `De acuerdo. ¿Hay algo más en lo que pueda ayudarte?`,
        'bot'
      );

    } else {
      agregarMensaje(
        `Por favor responde sí para ver el reporte de laboratorio, o no para continuar.`,
        'bot'
      );
    }
    return;
  }

  /* ── Estado idle: detección de intención ── */

  // Expediente / reporte — inicia flujo conversacional
  if (esIntentExpediente(lower)) {
    estadoBot = 'esperando_dni';
    agregarMensaje(
      `Para generar el reporte de expediente necesito identificar al paciente.\n\n¿Cuál es el número de DNI del paciente?`,
      'bot'
    );
    return;
  }

  // Intenciones simples (horario, registro, donación, emocional)
  const intencion = detectarIntencionSimple(mensaje);
  if (intencion) {
    agregarMensaje(RESPUESTAS_BOT[intencion].respuesta, 'bot');
    return;
  }

  // Fallback
  agregarMensaje(
    `No pude comprender tu mensaje. ¿Podrías reformularlo?\n\nPuedo ayudarte con:\n• Horarios de atención\n• Registro de pacientes\n• Donaciones\n• Reporte de expediente`,
    'bot'
  );
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

  const avatar       = document.createElement('div');
  avatar.className   = 'mensaje-avatar';
  if (tipo === 'bot') {
  avatar.innerHTML = '<img src="img/eva_chtb.jpg" alt="ALDIMI bot" />';
  } else {
  avatar.textContent = iniciales;
  }

  const burbuja       = document.createElement('div');
  burbuja.className   = 'mensaje-burbuja';

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

  const div    = document.createElement('div');
  div.className = 'mensaje bot mensaje-typing';
  div.id        = id;

  const avatar       = document.createElement('div');
  avatar.className   = 'mensaje-avatar';
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

  // Resetear estado conversacional
  estadoBot      = 'idle';
  pacienteActual = null;
}

//OCR

const OCR_SIMULADO = {
  DNI: {
    tipo: 'DNI',
    secciones: [
      {
        titulo: 'Datos del documento',
        campos: [
          { label: 'Nombres',      valor: 'JUAN CARLOS'  },
          { label: 'Apellidos',    valor: 'PÉREZ MAMANI' },
          { label: 'DNI',          valor: '45678912'     },
          { label: 'Fecha Nac.',   valor: '12/03/2015'   },
          { label: 'Lugar Nac.',   valor: 'CUSCO'        },
        ],
      },
    ],
    observacion: '✓ Documento identificado como DNI. Verifique los datos antes de guardar.',
  },
  HEMOGRAMA: {
    tipo: 'Reporte de Laboratorio',
    secciones: [
      {
        titulo: 'Datos del paciente',
        campos: [
          { label: 'Nombre',  valor: 'HUERTA DÍAZ RICHARD JOHNATAN' },
          { label: 'Edad',    valor: '35 Años'                      },
          { label: 'Sexo',    valor: 'Masculino'                    },
          { label: 'DNI',     valor: '44885622'                     },
        ],
      },
      {
        titulo: 'Información del examen',
        campos: [
          { label: 'Examen',          valor: 'HEMOGRAMA'           },
          { label: 'Fecha de muestra', valor: '11/04/2023'         },
          { label: 'Cliente',          valor: 'CLÍNICA SAN GABRIEL' },
          { label: 'Médico',           valor: 'CLÍNICA JESÚS DEL NORTE' },
        ],
      },
      {
        titulo: 'Resultados',
        esResultados: true,
        campos: [
          { label: 'Hemoglobina',              valor: '14.6 g/dL',      ref: '12.3 – 18.3',  ok: true  },
          { label: 'Hematocrito',              valor: '42.6 %',          ref: '39 – 52',      ok: true  },
          { label: 'Hematíes',                 valor: '5.18 ×10⁶/µL',   ref: '4.5 – 5.5',   ok: true  },
          { label: 'Leucocitos Totales',       valor: '4.7 ×10³/µL',    ref: '4.5 – 11',    ok: true  },
          { label: 'Linfocitos (%)',            valor: '42 %',            ref: '24 – 44',     ok: true  },
          { label: 'Neutrófilos Segmentados (%)', valor: '40 %',         ref: '35 – 66',     ok: true  },
          { label: 'Eosinófilos (%)',           valor: '8 %',             ref: '0 – 3',       ok: false, nota: 'Ligeramente elevado' },
          { label: 'Monocitos (%)',             valor: '9 %',             ref: '3 – 6',       ok: false, nota: 'Elevado'             },
        ],
      },
    ],
    observacion: '⚠️ Los eosinófilos y monocitos están ligeramente por encima del valor de referencia. Se recomienda seguimiento médico.',
  },
};

let archivoActual = null;

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

  document.getElementById('preview-nombre-archivo').textContent = archivo.name;

  const reader    = new FileReader();
  reader.onload   = (e) => {
    const img = document.getElementById('preview-imagen');
    img.src   = e.target.result;
    document.getElementById('preview-contenedor').classList.add('visible');
  };
  reader.readAsDataURL(archivo);

  const nombre = archivo.name.toLowerCase();
  let tipo     = 'Documento';
  if (nombre.includes('dni') || nombre.includes('identidad')) {
    tipo = 'DNI';
  } else if (nombre.includes('receta') || nombre.includes('medic') || nombre.includes('lab')) {
    tipo = 'Documento Médico';
  }

  document.getElementById('tipo-documento-badge').textContent = tipo;
  document.getElementById('tipo-documento-contenedor').classList.add('visible');
  document.getElementById('btn-procesar-ocr').classList.add('visible');
  document.getElementById('btn-limpiar-ocr').classList.add('visible');

  mostrarEstadoOCR('vacio');
}

function procesarOCR() {
  if (!archivoActual) return;

  const btnProcesar      = document.getElementById('btn-procesar-ocr');
  btnProcesar.textContent = 'Procesando...';
  btnProcesar.disabled    = true;

  mostrarEstadoOCR('procesando');

  const delay = 1500 + Math.random() * 1000;
  setTimeout(() => {
    btnProcesar.textContent = 'Extraer datos';
    btnProcesar.disabled    = false;

    const nombre = archivoActual.name.toLowerCase();
    const datos  = (nombre.includes('dni') || nombre.includes('identidad'))
      ? OCR_SIMULADO.DNI
      : OCR_SIMULADO.HEMOGRAMA;

    mostrarResultadoOCR(datos);
  }, delay);
}

function mostrarResultadoOCR(datos) {
  const contenedorCampos     = document.getElementById('ocr-campos');
  contenedorCampos.innerHTML = '';

  datos.secciones.forEach(seccion => {
    // Título de sección
    const titulo       = document.createElement('p');
    titulo.className   = 'ocr-seccion-titulo';
    titulo.textContent = seccion.titulo;
    contenedorCampos.appendChild(titulo);

    if (seccion.esResultados) {
      // Tabla de resultados con estado visual
      seccion.campos.forEach(campo => {
        const div       = document.createElement('div');
        div.className   = 'ocr-campo ocr-resultado' + (campo.ok ? '' : ' ocr-resultado--alt');

        // Fila superior: label + valor + badge estado
        const fila      = document.createElement('div');
        fila.className  = 'ocr-resultado-fila';

        const label         = document.createElement('label');
        label.textContent   = campo.label;

        const input         = document.createElement('input');
        input.type          = 'text';
        input.value         = campo.valor;
        input.readOnly      = true;

        const badge         = document.createElement('span');
        badge.className     = 'ocr-resultado-badge ' + (campo.ok ? 'badge-ok' : 'badge-alt');
        badge.textContent = campo.ok ? 'Normal' : (campo.nota || 'Fuera de rango');

        fila.appendChild(label);
        fila.appendChild(input);
        fila.appendChild(badge);
        div.appendChild(fila);

        // Referencia
        const ref       = document.createElement('span');
        ref.className   = 'ocr-resultado-ref';
        ref.textContent = 'Ref: ' + campo.ref;
        div.appendChild(ref);

        contenedorCampos.appendChild(div);
      });

    } else {
      // Campos normales
      seccion.campos.forEach(campo => {
        const div         = document.createElement('div');
        div.className     = 'ocr-campo';

        const label       = document.createElement('label');
        label.textContent = campo.label;

        const input       = document.createElement('input');
        input.type        = 'text';
        input.value       = campo.valor;
        input.readOnly    = true;

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

function guardarDatos() {
  const campos = document.querySelectorAll('#ocr-campos .ocr-campo');
  const datos  = {};

  campos.forEach(campo => {
    const key   = campo.querySelector('label').textContent;
    const val   = campo.querySelector('input').value;
    datos[key]  = val;
  });

  console.log('Datos a guardar:', datos);

  const statDocs = document.getElementById('stat-documentos');
  if (statDocs) statDocs.textContent = parseInt(statDocs.textContent) + 1;

  alert('✓ Datos guardados correctamente en el sistema.');
  limpiarOCR();
}

function limpiarOCR() {
  archivoActual = null;

  const inputImg = document.getElementById('input-imagen');
  if (inputImg) inputImg.value = '';

  document.getElementById('preview-contenedor').classList.remove('visible');
  document.getElementById('preview-imagen').src             = '';
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