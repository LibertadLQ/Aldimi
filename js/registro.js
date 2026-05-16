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

function togglePass(inputId) {
  const inp = document.getElementById(inputId);
  const btn = inp.nextElementSibling;
  if (inp.type === 'password') {
    inp.type = 'text';
    btn.textContent = 'Ocultar';
  } else {
    inp.type = 'password';
    btn.textContent = 'Mostrar';
  }
}


function esEmailValido(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

//LOGIN
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
    mostrarAlerta('error', 'Correo o contraseña incorrectos.');
    mostrarError('error-login-email', 'login-email', true);
    mostrarError('error-login-pass',  'login-pass',  true);
  }
}


//REGISTRO
function handleRegistro() {
  ocultarAlerta();

  const nombre   = document.getElementById('reg-nombre').value.trim();
  const apellido = document.getElementById('reg-apellido').value.trim();
  const email    = document.getElementById('reg-email').value.trim();
  const pass     = document.getElementById('reg-pass').value;
  const pass2    = document.getElementById('reg-pass2').value;
  const rol      = document.querySelector('input[name="rol"]:checked')?.value;

  limpiarErrores([
    { error: 'error-reg-nombre',   input: 'reg-nombre'   },
    { error: 'error-reg-apellido', input: 'reg-apellido' },
    { error: 'error-reg-email',    input: 'reg-email'    },
    { error: 'error-reg-pass',     input: 'reg-pass'     },
    { error: 'error-reg-pass2',    input: 'reg-pass2'    },
  ]);

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

  if (hayError) return;

  if (USUARIOS[email]) {
    mostrarAlerta('error', 'Este correo ya está registrado.');
    mostrarError('error-reg-email', 'reg-email', true);
    return;
  }

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

  setTimeout(() => switchTab('login'), 1200);
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