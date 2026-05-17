document.addEventListener('DOMContentLoaded', () => {
  cargarUsuario();
  mostrarFecha();
  mostrarSeccion('inicio');
  mostrarEstadoOCR('vacio');
});


/*  Cargar datos de sesión */
function cargarUsuario() {
  const raw = localStorage.getItem('aldimi_usuario');
  const usuario = raw ? JSON.parse(raw) : {
    nombre: 'Administrador',
    rol:    'admin',
    email:  'admin@aldimi.org',
  };

  // Saludo en inicio
  const saludo = document.getElementById('saludo-usuario');
  if (saludo) saludo.textContent = `Bienvenido, ${usuario.nombre.split(' ')[0]}`;

  // Nombre y rol en sidebar
  const elNombre = document.getElementById('usuario-nombre');
  const elRol    = document.getElementById('usuario-rol');
  if (elNombre) elNombre.textContent = usuario.nombre;
  if (elRol)    elRol.textContent    = usuario.rol;

  // Avatar con iniciales
  const elAvatar = document.getElementById('usuario-avatar');
  if (elAvatar) {
    const partes   = usuario.nombre.trim().split(' ');
    const iniciales = (partes[0][0] + (partes[1] ? partes[1][0] : '')).toUpperCase();
    elAvatar.textContent = iniciales;
  }
}

function cerrarSesion() {
  localStorage.removeItem('aldimi_usuario');
  // Redirige al login
  window.location.href = 'index.html';
  alert('Sesión cerrada. Redirigiendo al login...');
}

function mostrarFecha() {
  const el = document.getElementById('fecha-hoy');
  if (!el) return;
  const hoy = new Date();
  const opciones = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  el.textContent = hoy.toLocaleDateString('es-PE', opciones);
}

function mostrarSeccion(nombre) {
  // Ocultar todas las secciones
  document.querySelectorAll('.seccion').forEach(s => s.classList.remove('activa'));

  // Desactivar todos los botones del nav
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('activo'));

  // Mostrar sección seleccionada
  const seccion = document.getElementById('seccion-' + nombre);
  if (seccion) seccion.classList.add('activa');

  // Activar botón correspondiente
  const btn = document.querySelector(`.nav-btn[data-seccion="${nombre}"]`);
  if (btn) btn.classList.add('activo');
}


//CHATBOT 
const RESPUESTAS_BOT = {
  HORARIO: {
    palabras: ['horario','hora','visita','apertura','cierre','atiende','abren','abierto','cuando'],
    respuesta: '📅 El horario de visitas del Albergue ALDIMI es:\n\n• Lunes a Sábado: 9:00 a.m. a 6:00 p.m.\n\n¿Desea información sobre algún otro servicio?',
  },
  REGISTRO: {
    palabras: ['registrar','registro','ingreso','documentos','admisión','admision','paciente','inscribir','nuevo'],
    respuesta: '👤 Para registrar un paciente necesitas:\n\n• DNI del paciente y del apoderado\n• Diagnóstico médico actualizado\n• Documento de pobreza (si aplica)\n\nPuedes usar el módulo "Leer Documento" para digitalizar el DNI automáticamente.',
  },
  DONACION: {
    palabras: ['donar','donación','donacion','donaciones','ropa','yape','apoyo','transferencia','cuenta','ayuda','plin'],
    respuesta: '❤️ ¡Gracias por querer apoyar a ALDIMI!\n\nPuedes donar mediante:\n• Yape / Plin: 999-000-111\n• Transferencia bancaria: Cta. 123-456789\n• Donación de ropa y útiles: sede central\n\n¿Deseas más información?',
  },
  EXPEDIENTE: {
    palabras: ['expediente','historial','buscar paciente','datos del paciente','consultar','ver paciente'],
    respuesta: '🔍 Para consultar el expediente de un paciente indica:\n\n• Su número de DNI, o\n• Su ID de paciente (ej: P-001)\n\n¿Qué paciente deseas buscar?',
  },
  ALERTAS: {
    palabras: ['alertas','alerta','pendientes','riesgos','notificaciones'],
    respuesta: '🔔 Actualmente hay 3 alertas pendientes:\n\n• P-004: Riesgo emocional alto\n• P-007: No ha comido en 2 días\n• P-011: Aislamiento social detectado\n\nEl equipo psicosocial ha sido notificado.',
  },
  EMOCIONAL: {
    palabras: ['deprimido','ansiedad','triste','no quiero vivir','desesperado','llora','asustado','sin salida','suicidio'],
    respuesta: '⚠️ Se ha detectado una posible situación de riesgo emocional.\n\nSe registrará una alerta para el equipo de soporte psicosocial. El personal evaluará el caso a la brevedad.\n\n¿Puede indicar el ID del paciente para asociar la alerta?',
  },
};

// Detectar intención del mensaje
function detectarIntencion(mensaje) {
  const lower = mensaje.toLowerCase();
  let mejorIntencion = null;
  let mejorPuntaje   = 0;

  for (const [intencion, datos] of Object.entries(RESPUESTAS_BOT)) {
    const coincidencias = datos.palabras.filter(p => lower.includes(p)).length;
    const puntaje = coincidencias / datos.palabras.length;
    if (puntaje > mejorPuntaje) {
      mejorPuntaje   = puntaje;
      mejorIntencion = intencion;
    }
  }

  // Si el puntaje es muy bajo, fallback
  if (mejorPuntaje < 0.05) return null;
  return mejorIntencion;
}

// Enviar mensaje del usuario
function enviarMensaje() {
  const input   = document.getElementById('chat-input');
  const mensaje = input.value.trim();
  if (!mensaje) return;

  // Mostrar mensaje del usuario
  agregarMensaje(mensaje, 'usuario');
  input.value = '';

  // Deshabilitar input mientras responde
  input.disabled = true;
  document.getElementById('btn-enviar-chat').disabled = true;

  // Mostrar typing indicator
  const typingId = mostrarTyping();

  // Simular delay de respuesta (como si llamara a la API)
  const delay = 800 + Math.random() * 600;
  setTimeout(() => {
    quitarTyping(typingId);
    responderBot(mensaje);
    input.disabled = false;
    document.getElementById('btn-enviar-chat').disabled = false;
    input.focus();
  }, delay);
}

// Responder según intención
function responderBot(mensaje) {
  const intencion = detectarIntencion(mensaje);

  if (intencion) {
    const texto = RESPUESTAS_BOT[intencion].respuesta;
    agregarMensaje(texto, 'bot');
  } else {
    agregarMensaje(
      '❓ No pude comprender tu mensaje. ¿Podrías reformularlo?\n\nPuedo ayudarte con:\n• Horarios de atención\n• Registro de pacientes\n• Donaciones\n• Expediente de paciente\n• Alertas pendientes',
      'bot'
    );
  }
}

// Agregar burbuja al chat
function agregarMensaje(texto, tipo) {
  const contenedor = document.getElementById('chat-mensajes');
  const raw = localStorage.getItem('aldimi_usuario');
  const usuario = raw ? JSON.parse(raw) : { nombre: 'Usuario' };
  const partes   = usuario.nombre.trim().split(' ');
  const iniciales = (partes[0][0] + (partes[1] ? partes[1][0] : '')).toUpperCase();

  const div = document.createElement('div');
  div.className = `mensaje ${tipo}`;

  // Avatar
  const avatar = document.createElement('div');
  avatar.className = 'mensaje-avatar';
  avatar.textContent = tipo === 'bot' ? '🤖' : iniciales;

  // Burbuja
  const burbuja = document.createElement('div');
  burbuja.className = 'mensaje-burbuja';

  // Convertir saltos de línea y bullets en HTML
  const html = texto
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .split('\n')
    .map(linea => {
      if (linea.startsWith('• ')) {
        return `<li>${linea.slice(2)}</li>`;
      }
      return linea ? `<p>${linea}</p>` : '';
    })
    .join('');

  burbuja.innerHTML = html.replace(/(<li>.*<\/li>)+/gs, match => `<ul>${match}</ul>`);

  div.appendChild(avatar);
  div.appendChild(burbuja);
  contenedor.appendChild(div);

  // Scroll al último mensaje
  contenedor.scrollTop = contenedor.scrollHeight;
}

// Mostrar typing indicator
function mostrarTyping() {
  const contenedor = document.getElementById('chat-mensajes');
  const id = 'typing-' + Date.now();

  const div = document.createElement('div');
  div.className = 'mensaje bot mensaje-typing';
  div.id = id;

  const avatar = document.createElement('div');
  avatar.className = 'mensaje-avatar';
  avatar.textContent = '👾';

  const burbuja = document.createElement('div');
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

// Botones de sugerencias rápidas
function enviarSugerencia(btn) {
  const input = document.getElementById('chat-input');
  input.value = btn.textContent;
  enviarMensaje();
}

// Limpiar chat
function limpiarChat() {
  const contenedor = document.getElementById('chat-mensajes');
  // Dejar solo el mensaje de bienvenida
  const bienvenida = document.getElementById('mensaje-bienvenida');
  contenedor.innerHTML = '';
  if (bienvenida) contenedor.appendChild(bienvenida);
}


// OCR 

// Datos simulados por tipo de documento
const OCR_SIMULADO = {
  DNI: {
    tipo: 'DNI',
    campos: [
      { label: 'Nombres',      valor: 'JUAN CARLOS'   },
      { label: 'Apellidos',    valor: 'PÉREZ MAMANI'  },
      { label: 'DNI',          valor: '45678912'      },
      { label: 'Fecha Nac.',   valor: '12/03/2015'    },
      { label: 'Lugar Nac.',   valor: 'CUSCO'         },
    ],
    observacion: '✓ Documento identificado como DNI. Verifique los datos antes de guardar.',
  },
  RECETA: {
    tipo: 'Documento Médico',
    campos: [
      { label: 'Paciente',     valor: 'JUAN CARLOS PÉREZ' },
      { label: 'Médico',       valor: 'Dr. García López'   },
      { label: 'Diagnóstico',  valor: 'Leucemia linfoblástica aguda' },
      { label: 'Medicamento',  valor: 'Vincristina 1.5mg/m²'         },
      { label: 'Fecha',        valor: new Date().toLocaleDateString('es-PE') },
    ],
    observacion: '✓ Documento identificado como receta médica. Verifique los datos antes de guardar.',
  },
};

let archivoActual = null;

// Cargar imagen desde el input
function cargarImagen(evento) {
  const archivo = evento.target.files[0];
  if (!archivo) return;
  procesarArchivo(archivo);
}

// Cargar imagen por drag & drop
function soltarArchivo(evento) {
  evento.preventDefault();
  document.getElementById('zona-subir').classList.remove('arrastrando');
  const archivo = evento.dataTransfer.files[0];
  if (!archivo) return;

  // Validar tipo
  const tiposPermitidos = ['image/jpeg', 'image/png'];
  if (!tiposPermitidos.includes(archivo.type)) {
    alert('Solo se permiten imágenes JPG o PNG.');
    return;
  }

  // Validar tamaño (5MB)
  if (archivo.size > 5 * 1024 * 1024) {
    alert('La imagen supera los 5MB permitidos.');
    return;
  }

  procesarArchivo(archivo);
}

// Mostrar preview y preparar el OCR
function procesarArchivo(archivo) {
  archivoActual = archivo;

  // Mostrar nombre
  document.getElementById('preview-nombre-archivo').textContent = archivo.name;

  // Mostrar preview
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = document.getElementById('preview-imagen');
    img.src = e.target.result;
    document.getElementById('preview-contenedor').classList.add('visible');
  };
  reader.readAsDataURL(archivo);

  // Detectar tipo por nombre del archivo (simulación)
  const nombre = archivo.name.toLowerCase();
  let tipo = 'Documento';
  if (nombre.includes('dni') || nombre.includes('identidad')) {
    tipo = 'DNI';
  } else if (nombre.includes('receta') || nombre.includes('medic') || nombre.includes('lab')) {
    tipo = 'Documento Médico';
  }

  document.getElementById('tipo-documento-badge').textContent = tipo;
  document.getElementById('tipo-documento-contenedor').classList.add('visible');

  // Mostrar botones
  document.getElementById('btn-procesar-ocr').classList.add('visible');
  document.getElementById('btn-limpiar-ocr').classList.add('visible');

  // Resetear resultado
  mostrarEstadoOCR('vacio');
}

// Procesar OCR (simulado)
function procesarOCR() {
  if (!archivoActual) return;

  const btnProcesar = document.getElementById('btn-procesar-ocr');
  btnProcesar.textContent = 'Procesando...';
  btnProcesar.disabled    = true;

  // Mostrar spinner
  mostrarEstadoOCR('procesando');

  // Simular delay de la API
  const delay = 1500 + Math.random() * 1000;
  setTimeout(() => {
    btnProcesar.textContent = 'Extraer datos';
    btnProcesar.disabled    = false;

    // Decidir qué datos simular según nombre del archivo
    const nombre = archivoActual.name.toLowerCase();
    let datos;
    if (nombre.includes('receta') || nombre.includes('medic') || nombre.includes('lab')) {
      datos = OCR_SIMULADO.RECETA;
    } else {
      datos = OCR_SIMULADO.DNI;
    }

    mostrarResultadoOCR(datos);
  }, delay);
}

// Mostrar resultado en los campos
function mostrarResultadoOCR(datos) {
  const contenedorCampos = document.getElementById('ocr-campos');
  contenedorCampos.innerHTML = '';

  datos.campos.forEach(campo => {
    const div = document.createElement('div');
    div.className = 'ocr-campo';

    const label = document.createElement('label');
    label.textContent = campo.label;

    const input = document.createElement('input');
    input.type      = 'text';
    input.value     = campo.valor;
    input.readOnly  = true;

    div.appendChild(label);
    div.appendChild(input);
    contenedorCampos.appendChild(div);
  });

  // Mostrar observación
  const obsEl = document.getElementById('ocr-observacion');
  const obsTxt = document.getElementById('ocr-observacion-texto');
  obsTxt.textContent = datos.observacion;
  obsEl.classList.add('visible');

  mostrarEstadoOCR('resultado');
}

// Habilitar edición de los campos extraídos
function habilitarEdicion() {
  const inputs = document.querySelectorAll('#ocr-campos input');
  inputs.forEach(inp => {
    inp.readOnly = false;
    inp.focus();
  });
  document.getElementById('btn-editar-ocr').textContent = 'Editando...';
  document.getElementById('btn-editar-ocr').disabled = true;
}

// Guardar datos (simulado)
function guardarDatos() {
  const campos  = document.querySelectorAll('#ocr-campos .ocr-campo');
  const datos   = {};

  campos.forEach(campo => {
    const key = campo.querySelector('label').textContent;
    const val = campo.querySelector('input').value;
    datos[key] = val;
  });

  // En producción: POST /api/pacientes con los datos
  console.log('Datos a guardar:', datos);

  // Actualizar el contador de documentos
  const statDocs = document.getElementById('stat-documentos');
  if (statDocs) statDocs.textContent = parseInt(statDocs.textContent) + 1;

  alert('✓ Datos guardados correctamente en el sistema.');
  limpiarOCR();
}

// Limpiar todo el módulo OCR
function limpiarOCR() {
  archivoActual = null;

  // Limpiar input de archivo
  const inputImg = document.getElementById('input-imagen');
  if (inputImg) inputImg.value = '';

  // Ocultar preview
  document.getElementById('preview-contenedor').classList.remove('visible');
  document.getElementById('preview-imagen').src = '';
  document.getElementById('preview-nombre-archivo').textContent = '';

  // Ocultar tipo
  document.getElementById('tipo-documento-contenedor').classList.remove('visible');
  document.getElementById('tipo-documento-badge').textContent = '';

  // Ocultar botones
  document.getElementById('btn-procesar-ocr').classList.remove('visible');
  document.getElementById('btn-limpiar-ocr').classList.remove('visible');

  // Resetear btn editar
  const btnEditar = document.getElementById('btn-editar-ocr');
  btnEditar.textContent = 'Editar datos';
  btnEditar.disabled    = false;

  // Ocultar observación
  document.getElementById('ocr-observacion').classList.remove('visible');

  // Volver al estado vacío
  mostrarEstadoOCR('vacio');
}

// Cambiar estado del panel resultado
function mostrarEstadoOCR(estado) {
  const estados = ['vacio', 'procesando', 'resultado', 'error'];
  estados.forEach(e => {
    const el = document.getElementById('ocr-estado-' + e);
    if (el) el.classList.toggle('visible', e === estado);
  });
}