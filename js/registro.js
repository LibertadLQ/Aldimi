const CODIGO_ADMIN = 'ALDIMI2024';

const USUARIOS_DEFAULT = {
  'admin@aldimi.org':      { pass: 'admin123',  rol: 'admin',      nombre: 'Administrador' },
  'voluntario@aldimi.org': { pass: 'vol123',    rol: 'voluntario', nombre: 'María Pérez'   }
};

const USUARIOS = JSON.parse(localStorage.getItem('aldimi_usuarios')) || { ...USUARIOS_DEFAULT };

function switchTab(tab) {
  const botones = document.querySelectorAll('#tabs button');
  botones[0].classList.toggle('active', tab === 'login');
  botones[1].classList.toggle('active', tab === 'registro');

  document.getElementById('panel-login').classList.toggle('activo', tab === 'login');
  document.getElementById('panel-registro').classList.toggle('activo', tab === 'registro');

  ocultarAlerta();
}

function mostrarAlerta(tipo, mensaje) {
  const el = document.getElementById('alerta-global');
  el.className = tipo === 'exito' ? 'exito' : 'error';
  el.textContent = (tipo === 'exito' ? '✓ ' : '✕ ') + mensaje;
}

function ocultarAlerta() {
  const el = document.getElementById('alerta-global');
  el.className = '';
  el.textContent = '';
}

function mostrarError(idError, idInput, mostrar) {
  const errEl = document.getElementById(idError);
  const inpEl = document.getElementById(idInput);
  if (errEl) errEl.classList.toggle('visible', mostrar);
  if (inpEl) inpEl.classList.toggle('error', mostrar);
}

function limpiarErrores(ids) {
  ids.forEach(({ error, input }) => mostrarError(error, input, false));
}

// Botón mostrar/ocultar contraseña con íconos SVG
function togglePass(inputId) {
  const inp = document.getElementById(inputId);
  const isPassword = inp.type === 'password';
  inp.type = isPassword ? 'text' : 'password';

  // Mapear inputId a los ids de los íconos correspondientes
  const sufijo = inputId === 'login-pass'  ? 'login-pass'
               : inputId === 'reg-pass'    ? 'reg-pass'
               : inputId === 'reg-pass2'   ? 'reg-pass2'
               : null;

  if (sufijo) {
    document.getElementById(`icon-show-${sufijo}`).style.display = isPassword ? 'none' : '';
    document.getElementById(`icon-hide-${sufijo}`).style.display = isPassword ? ''     : 'none';
  }
}

function esEmailValido(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// Rol condicional: muestra/oculta el campo de código admin
function onRolChange() {
  const rol = document.querySelector('input[name="rol"]:checked')?.value;
  const campo = document.getElementById('campo-codigo-admin');
  const input = document.getElementById('reg-codigo-admin');

  if (rol === 'admin') {
    campo.style.display = 'block';
  } else {
    campo.style.display = 'none';
    input.value = '';
    mostrarError('error-reg-codigo-admin', 'reg-codigo-admin', false);
  }
}

// Barra de fortaleza de contraseña
function calcularFortaleza(pass) {
  let score = 0;
  if (pass.length >= 8)                        score++;
  if (pass.length >= 12)                       score++;
  if (/[A-Z]/.test(pass) && /[a-z]/.test(pass)) score++;
  if (/[0-9]/.test(pass))                      score++;
  if (/[^A-Za-z0-9]/.test(pass))              score++;

  if (score <= 1) return { nivel: 1, texto: 'Débil' };
  if (score === 2) return { nivel: 2, texto: 'Regular' };
  if (score === 3) return { nivel: 3, texto: 'Buena' };
  return { nivel: 4, texto: 'Fuerte' };
}

function actualizarFortaleza() {
  const pass = document.getElementById('reg-pass').value;
  const wrap = document.getElementById('fortaleza-wrap');
  const barra = document.getElementById('fortaleza-barra');
  const label = document.getElementById('fortaleza-label');

  if (!pass) {
    wrap.className = '';
    barra.className = '';
    label.textContent = '';
    return;
  }

  const { nivel, texto } = calcularFortaleza(pass);
  wrap.className = 'visible';
  barra.className = `fortaleza-${nivel}`;
  label.textContent = texto;
}

// Estado de carga en botones
function setBtnCargando(btnSelector, cargando, textoOriginal) {
  const btn = document.querySelector(btnSelector);
  if (!btn) return;
  btn.disabled = cargando;
  btn.textContent = cargando ? 'Cargando...' : textoOriginal;
}


// ── LOGIN ──
function handleLogin() {
  ocultarAlerta();

  const email = document.getElementById('login-email').value.trim();
  const pass  = document.getElementById('login-pass').value;

  limpiarErrores([
    { error: 'error-login-email', input: 'login-email' },
    { error: 'error-login-pass',  input: 'login-pass'  },
  ]);

  let hayError = false;

  if (!esEmailValido(email)) {
    mostrarError('error-login-email', 'login-email', true);
    hayError = true;
  }

  if (!pass) {
    mostrarError('error-login-pass', 'login-pass', true);
    hayError = true;
  }

  if (hayError) return;

  setBtnCargando('button[onclick="handleLogin()"]', true, 'Ingresar al sistema');

  // Simula latencia de red (quitar el setTimeout si hay backend real)
  setTimeout(() => {
    const usuario = USUARIOS[email];

    if (usuario && usuario.pass === pass) {
      localStorage.setItem('aldimi_usuario', JSON.stringify({
        email,
        nombre: usuario.nombre,
        rol:    usuario.rol,
      }));

      mostrarAlerta('exito', `Bienvenido, ${usuario.nombre}. Redirigiendo...`);
      setTimeout(() => { window.location.href = 'chatbot.html'; }, 800);

    } else {
      setBtnCargando('button[onclick="handleLogin()"]', false, 'Ingresar al sistema');
      mostrarAlerta('error', 'Correo o contraseña incorrectos.');
      mostrarError('error-login-email', 'login-email', true);
      mostrarError('error-login-pass',  'login-pass',  true);
    }
  }, 600);
}


// ── REGISTRO ──
function handleRegistro() {
  ocultarAlerta();

  const nombre   = document.getElementById('reg-nombre').value.trim();
  const apellido = document.getElementById('reg-apellido').value.trim();
  const email    = document.getElementById('reg-email').value.trim();
  const pass     = document.getElementById('reg-pass').value;
  const pass2    = document.getElementById('reg-pass2').value;
  const rol      = document.querySelector('input[name="rol"]:checked')?.value;
  const codigo   = document.getElementById('reg-codigo-admin').value.trim();

  const camposBase = [
    { error: 'error-reg-nombre',   input: 'reg-nombre'   },
    { error: 'error-reg-apellido', input: 'reg-apellido' },
    { error: 'error-reg-email',    input: 'reg-email'    },
    { error: 'error-reg-pass',     input: 'reg-pass'     },
    { error: 'error-reg-pass2',    input: 'reg-pass2'    },
    { error: 'error-reg-codigo-admin', input: 'reg-codigo-admin' },
  ];
  limpiarErrores(camposBase);

  let hayError = false;

  if (!nombre) {
    mostrarError('error-reg-nombre', 'reg-nombre', true);
    hayError = true;
  }

  if (!apellido) {
    mostrarError('error-reg-apellido', 'reg-apellido', true);
    hayError = true;
  }

  if (!esEmailValido(email)) {
    mostrarError('error-reg-email', 'reg-email', true);
    hayError = true;
  }

  if (pass.length < 8) {
    mostrarError('error-reg-pass', 'reg-pass', true);
    hayError = true;
  }

  if (pass !== pass2 || !pass2) {
    mostrarError('error-reg-pass2', 'reg-pass2', true);
    hayError = true;
  }

  // Validar código si el rol es admin
  if (rol === 'admin' && codigo !== CODIGO_ADMIN) {
    mostrarError('error-reg-codigo-admin', 'reg-codigo-admin', true);
    hayError = true;
  }

  if (hayError) return;

  if (USUARIOS[email]) {
    mostrarAlerta('error', 'Este correo ya está registrado.');
    mostrarError('error-reg-email', 'reg-email', true);
    return;
  }

  setBtnCargando('button[onclick="handleRegistro()"]', true, 'Crear cuenta');

  setTimeout(() => {
    USUARIOS[email] = {
      pass,
      rol,
      nombre: nombre + ' ' + apellido,
    };

    localStorage.setItem('aldimi_usuarios', JSON.stringify(USUARIOS));

    mostrarAlerta('exito', `Cuenta creada para ${nombre}. Ahora puedes iniciar sesión.`);

    document.getElementById('reg-nombre').value   = '';
    document.getElementById('reg-apellido').value = '';
    document.getElementById('reg-email').value    = '';
    document.getElementById('reg-pass').value     = '';
    document.getElementById('reg-pass2').value    = '';
    document.getElementById('reg-codigo-admin').value = '';
    actualizarFortaleza();

    setBtnCargando('button[onclick="handleRegistro()"]', false, 'Crear cuenta');
    setTimeout(() => switchTab('login'), 1200);
  }, 600);
}


document.addEventListener('DOMContentLoaded', () => {
  switchTab('login');

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const loginActivo = document.getElementById('panel-login').classList.contains('activo');
    if (loginActivo) handleLogin();
    else             handleRegistro();
  });
});