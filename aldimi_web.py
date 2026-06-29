# aldimi_web.py — Version liviana para FastAPI/Render
# Solo contiene NLP y funciones OCR, sin Google Drive, sin Colab, sin pipelines

import os, re, json, time, math, hashlib, datetime, logging, tempfile
import numpy as np

# ── Imports opcionales con fallback ──────────────────────────────────────────
_NLTK_OK = _TESSERACT_OK = _BCRYPT_OK = _EASYOCR_OK = False

try:
    from nltk.corpus import stopwords as _sw_corpus
    from nltk.tokenize import word_tokenize as _wt
    _NLTK_OK = True
except: pass

try:
    import pytesseract
    pytesseract.get_tesseract_version()
    _TESSERACT_OK = True
except: pass

try:
    import bcrypt as _bcrypt
    _BCRYPT_OK = True
except: pass

try:
    import easyocr as _easyocr_lib
    _EASYOCR_OK = True
except: pass

try:
    import cv2
except: cv2 = None

try:
    from PIL import Image as _PIL_Image
except: _PIL_Image = None

_log = logging.getLogger('ALDIMI_WEB')
logging.basicConfig(level=logging.WARNING)

OCR_LANG = 'spa+eng'

# Base de datos en memoria
_BD = {}
DB_FOLDER = os.environ.get('ALDIMI_DB_PATH', '/tmp/ALDIMI_DB')
DB_JSON_PATH = os.path.join(DB_FOLDER, 'aldimi_pacientes.json')
os.makedirs(DB_FOLDER, exist_ok=True)

# Metricas simples
SYSTEM_METRICS = {
    'nlp': {'total': 0, 'reconocidos': 0, 'fallbacks': 0, 'tiempo_ms': 0.0,
            'por_intencion': {k: {'total':0,'correctos':0} for k in
                ['HORARIO','ADMISION','DONACION','EXPEDIENTE','ALERTA','EMOCIONAL','REGLAMENTO']}},
}

# ── Stopwords ────────────────────────────────────────────────────────────────
_STOPWORDS_ES = {
    'de','la','que','el','en','y','a','los','del','se','las','por','un','para',
    'con','no','una','su','al','lo','como','mas','pero','sus','le','ya','o',
    'este','si','porque','esta','entre','cuando','muy','sin','sobre','tambien',
    'me','hasta','hay','donde','quien','desde','nos','uno','mi','que','ser',
    'es','si','te','tiene',
}

def _get_sw():
    if _NLTK_OK:
        try: return set(_sw_corpus.words('spanish'))
        except: pass
    return _STOPWORDS_ES

def _tokenize(text):
    if _NLTK_OK:
        try: return _wt(text.lower(), language='spanish')
        except: pass
    return re.findall(r'\b[a-záéíóúüñ]{2,}\b', text.lower())

# ── Base de conocimiento ─────────────────────────────────────────────────────
KNOWLEDGE_BASE = {
    'HORARIO': (
        'El horario de atención del Albergue ALDIMI es:\n'
        '   Lunes a Sábado: 9:00 a.m. a 6:00 p.m.\n'
        '   Domingos y feriados: CERRADO.\n'
        '   Urgencias: número de guardia 24/7.\n'
        '¿Desea información sobre algún otro servicio?'
    ),
    'ADMISION': (
        'Para registrar a un paciente necesita:\n'
        '   1. Código CIU del DNI del paciente.\n'
        '   2. Imagen del documento de identidad (PNG/JPG).\n'
        '   El sistema extraerá los datos con OCR + CNN automáticamente.\n'
        'Escriba REGISTRO para iniciar el proceso.'
    ),
    'DONACION': (
        'Canales de donación del Albergue ALDIMI:\n'
        '   • Yape / Plin: 999-888-777\n'
        '   • BCP: Cuenta 123-456789-0-12\n'
        '   • Interbank: 200-3456789-012\n'
        '   • En especie: Ropa, alimentos, medicamentos (lunes a sábado 9am-5pm).\n'
        '   • Voluntariado: coordinacion@aldimi.org'
    ),
    'EXPEDIENTE': (
        'Para consultar el expediente, indique el CIU del paciente.\n'
        '   Formato Perú: 8 dígitos (ej: 42951703)\n'
        '   Formato USA : letra + 6 dígitos (ej: W839927)\n'
        'Podrá ver: datos personales, análisis clínicos y alertas detectadas.'
    ),
    'ALERTA': (
        'Se ha detectado una situación de riesgo emocional.\n'
        'Se registrará una alerta para el equipo de soporte psicosocial.\n'
        'El personal evaluará el caso a la brevedad.\n'
        'En emergencias llame al número de guardia 24/7.'
    ),
    'REGLAMENTO': (
        'Reglamento del Albergue ALDIMI:\n'
        '   ADMISIÓN: Solo pacientes oncológicos con referencia médica válida.\n'
        '   PERMANENCIA: Máxima 30 días prorrogables según evaluación médica.\n'
        '   HORARIO silencio: 10pm-6am.\n'
        '   ALIMENTACIÓN: desayuno, almuerzo y cena incluidos.\n'
        '   PROHIBIDO: alcohol, cigarrillos, visitas no autorizadas.\n'
        '   VISITAS: Solo familiares directos, sábados 3pm-5pm.'
    ),
    'SERVICIOS': (
        'Servicios del Albergue ALDIMI:\n'
        '   • Hospedaje gratuito para paciente y un acompañante.\n'
        '   • Alimentación: desayuno, almuerzo y cena.\n'
        '   • Apoyo psicosocial y consejería.\n'
        '   • Gestión de citas médicas en hospitales de referencia.\n'
        '   • Lavandería 2 veces por semana.\n'
        '   • Acceso a internet y sala de esparcimiento.'
    ),
    'REQUISITOS': (
        'Requisitos para ingresar al Albergue ALDIMI:\n'
        '   • Diagnóstico oncológico confirmado (informe médico).\n'
        '   • DNI original del paciente y acompañante.\n'
        '   • Carta de referencia del hospital tratante.\n'
        '   • No contar con familiares en Lima que brinden alojamiento.\n'
        '   • Llenar formulario de admisión al ingreso.'
    ),
    'VISITAS': (
        'Política de visitas del Albergue ALDIMI:\n'
        '   • Solo familiares directos (máx. 2 personas simultáneas).\n'
        '   • Horario: sábados 3pm-5pm.\n'
        '   • Niños menores de 12 años no ingresan a habitaciones.\n'
        '   • Toda visita debe registrarse en recepción con DNI.'
    ),
    'EMOCIONAL': (
        'Entiendo que puede estar pasando por un momento difícil.\n'
        'El equipo de apoyo psicosocial del Albergue ALDIMI está disponible.\n'
        'En emergencias llame al número de guardia 24/7.\n'
        'No está solo/a.'
    ),
    'FALLBACK': (
        'No pude entender su consulta. Puede escribir:\n'
        '   horario | registro | donaciones | expedientes | alertas\n'
        '   reglamento | servicios | requisitos | visitas'
    ),
}

FAQ_REGLAMENTO = {
    r'(edad|cuantos.anos|requisito|quien.puede)': (
        'ADMISIÓN: Pacientes oncológicos mayores de 18 años con referencia médica válida. '
        'Se admite un acompañante adulto por paciente.'
    ),
    r'(visita|visitar|familiar|quien.viene|cuando.viene)': (
        'VISITAS: Solo familiares directos (padres, hijos, cónyuge). '
        'Deben coordinar previamente con la recepción. '
        'Horario: sábados de 3:00pm a 5:00pm.'
    ),
    r'(tiempo|cuanto.tiempo|permanencia|cuanto.puede.quedar|plazo)': (
        'PERMANENCIA: Máxima 30 días prorrogables según evaluación médica. '
        'El equipo evaluará cada caso al vencimiento del plazo.'
    ),
    r'(medic|doctor|salud|atencion.medica|cita)': (
        'ATENCIÓN MÉDICA: Evaluación médica semanal para todos los pacientes. '
        'Guardia médica disponible 24 horas ante emergencias.'
    ),
    r'(prohib|no.permit|regla|norma)': (
        'PROHIBICIONES en el albergue:\n'
        '   Sustancias tóxicas o alcohol\n'
        '   Violencia física o verbal\n'
        '   Salidas no autorizadas\n'
        '   Visitas no coordinadas\n'
        '   Ruido después de las 10pm'
    ),
    r'(donar|donacion|ayudar|contribuir|apoyo)': 'Ver canales de donación: escriba "donaciones".',
    r'(horario|hora|cuando.atiende|abierto)': 'Ver horarios: escriba "horario".',
}

INTENT_KEYWORDS = {
    'HORARIO'   : ['horario','hora','apertura','cierre','cuando','abren','atienden'],
    'ADMISION'  : ['registrar','registro','ingreso','documentos','admision','nuevo','inscribir','agregar'],
    'DONACION'  : ['donar','donacion','yape','cuenta','ropa','dinero','transferencia','ayuda','contribuir'],
    'EXPEDIENTE': ['expediente','historial','consultar','buscar','ver','datos','paciente','ciu'],
    'ALERTA'    : ['alerta','alertas','pendiente','riesgo','critico','notificacion'],
    'EMOCIONAL' : ['deprimido','triste','llora','ansiedad','no quiero','suicidio','morir','sufre','crisis'],
    'REGLAMENTO': ['reglamento','normas','reglas','politica','conducta','prohibido'],
    'SERVICIOS' : ['servicios','ofrecen','tiene','alimentacion','lavanderia','wifi'],
    'REQUISITOS': ['requisitos','necesito','como ingresar','documentos necesarios'],
    'VISITAS'   : ['visitas','familiar','acompanante','quien puede visitar'],
}

NEGATIVE_WORDS = {
    'deprimido','triste','llora','ansiedad','morir','suicidio','desesperado',
    'angustia','dolor','sufre','aislado','decaido','crisis','abandono','vacio','sin salida',
}

POSITIVE_WORDS = {
    'mejora','bien','contento','feliz','progreso','avance','tranquilo',
    'recuperado','estable','alegre','animado','esperanza','familia',
}

# ── Funciones NLP ─────────────────────────────────────────────────────────────

def preprocess_text(text):
    t = str(text).lower()
    trans = str.maketrans('áéíóúüñ', 'aeiooun')
    t = t.translate(trans)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    tokens = _tokenize(t)
    sw = {s.translate(trans) for s in _get_sw()}
    return [tok for tok in tokens if tok not in sw and len(tok) > 1]

def _conf(tokens, intent_key):
    kws = INTENT_KEYWORDS.get(intent_key, [])
    if not tokens or not kws: return 0.0
    trans = str.maketrans('áéíóúüñ', 'aeiooun')
    kn = [k.translate(trans) for k in kws]
    hits = sum(1 for t in tokens if any(k in t or t in k for k in kn))
    if hits == 0: return 0.0
    base = {1: 0.80, 2: 0.90}.get(hits, 0.95)
    if len(tokens) <= 3: base = min(base + 0.05, 1.0)
    return round(base, 3)

def _sentiment_neg_score(tokens):
    if not tokens: return 0.0
    trans = str.maketrans('áéíóúüñ', 'aeiooun')
    neg = {w.translate(trans) for w in NEGATIVE_WORDS}
    h = sum(1 for t in tokens if t in neg)
    return -(h / len(tokens))

def buscar_faq_reglamento(msg):
    msg_norm = re.sub(r'[aeiouáéíóúüñ]', '.', str(msg).lower())
    for patron, resp in FAQ_REGLAMENTO.items():
        if re.search(patron, msg_norm):
            return resp
    return None

def detect_intent(msg):
    tokens = preprocess_text(msg)
    scores = {k: _conf(tokens, k) for k in INTENT_KEYWORDS}
    best = max(scores, key=scores.get)
    conf = scores[best]
    sent = _sentiment_neg_score(tokens)
    if sent < -0.15:
        return 'EMOCIONAL', round(abs(sent), 3)
    thresholds = {k: 0.75 for k in INTENT_KEYWORDS}
    thresholds.update({'ADMISION': 0.80, 'DONACION': 0.85})
    if best in thresholds and conf >= thresholds[best]:
        return best, conf
    return 'FALLBACK', conf

def chatbot_response_nlp(msg):
    t0 = time.time()
    faq = buscar_faq_reglamento(msg)
    if faq:
        SYSTEM_METRICS['nlp']['total'] += 1
        SYSTEM_METRICS['nlp']['reconocidos'] += 1
        return 'REGLAMENTO', 0.95, faq
    intent, conf = detect_intent(msg)
    SYSTEM_METRICS['nlp']['total'] += 1
    if intent != 'FALLBACK':
        SYSTEM_METRICS['nlp']['reconocidos'] += 1
    else:
        SYSTEM_METRICS['nlp']['fallbacks'] += 1
    resp = KNOWLEDGE_BASE.get(intent, KNOWLEDGE_BASE['FALLBACK'])
    return intent, conf, resp

# ── OCR ───────────────────────────────────────────────────────────────────────

_easyocr_reader = None

def _get_reader():
    """Retorna el reader de EasyOCR (singleton para no recargarlo cada vez)."""
    global _easyocr_reader
    if _easyocr_reader is None and _EASYOCR_OK:
        try:
            _easyocr_reader = _easyocr_lib.Reader(['es', 'en'], gpu=False, verbose=False)
            print('EasyOCR reader inicializado')
        except Exception as e:
            print(f'Error inicializando EasyOCR: {e}')
    return _easyocr_reader

def _extraer_texto_imagen(ruta):
    """Extrae texto de una imagen usando EasyOCR."""
    texto = ''
    reader = _get_reader()
    if reader:
        try:
            results = reader.readtext(ruta, detail=1)
            lines = [t for _, t, c in results if c >= 0.3]
            texto = '\n'.join(lines)
        except Exception as e:
            _log.warning(f'EasyOCR error: {e}')
    return texto

def clasificar_documento(texto):
    t = texto.upper()
    if re.search(r'\b(DNI|DOCUMENTO NACIONAL|REPUBLICA DEL PERU|RENIEC)\b', t):
        return 'DNI_PERU'
    if re.search(r'\b(DRIVER|LICENSE|IDENTIFICATION|STATE OF|USA|W\d{6})\b', t):
        return 'DNI_USA'
    if re.search(r'\b(HEMOGLOBINA|LEUCOCITOS|HEMATOCRITO|PLAQUETAS|GLUCOSA|LABORATORIO|ANALISIS|PCR|RESULTADO)\b', t):
        return 'LAB_REPORT'
    if re.search(r'\b(DIAGNOSTICO|MEDICO|CLINICA|HOSPITAL|INFORME|PACIENTE)\b', t):
        return 'INFORME_MEDICO'
    return 'DESCONOCIDO'

def extraer_ciu(texto, tipo=None):
    if tipo == 'DNI_USA' or re.search(r'\b[Ww]\d{6}\b', texto):
        m = re.search(r'\b([Ww]\d{6})\b', texto)
        if m: return m.group(1).upper()
    m = re.search(r'\b(\d{8})\b', texto)
    if m: return m.group(1)
    return ''

def extraer_nombre_apellido(texto, tipo_dni):
    nombres, apellidos = '', ''
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    for linea in lineas:
        l = linea.upper()
        if 'NOMBRES' in l or 'PRENOMBRES' in l:
            partes = re.split(r'[:\/]', linea, 1)
            if len(partes) > 1:
                nombres = partes[1].strip()
        if 'APELLIDOS' in l or 'APELLIDO' in l:
            partes = re.split(r'[:\/]', linea, 1)
            if len(partes) > 1:
                apellidos = partes[1].strip()
    return nombres, apellidos

def extraer_fecha_nacimiento(texto, tipo_dni):
    patrones = [
        r'\b(\d{2}/\d{2}/\d{4})\b',
        r'\b(\d{2}-\d{2}-\d{4})\b',
        r'\b(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\w*\s+\d{4})\b',
    ]
    for p in patrones:
        m = re.search(p, texto, re.IGNORECASE)
        if m: return m.group(1)
    return ''

def procesar_imagen_dni(ruta, ciu_hint=''):
    """Procesa imagen de DNI y retorna datos extraídos."""
    texto = _extraer_texto_imagen(ruta)
    if not texto:
        return None
    tipo = clasificar_documento(texto)
    if tipo not in ('DNI_PERU', 'DNI_USA'):
        tipo = 'DNI_PERU'
    ciu = extraer_ciu(texto, tipo) or ciu_hint
    nombres, apellidos = extraer_nombre_apellido(texto, tipo)
    fecha = extraer_fecha_nacimiento(texto, tipo)
    if not ciu:
        return None
    return {
        'ciu': ciu,
        'tipo_dni': tipo,
        'nombres': nombres or 'NO_DETECTADO',
        'apellidos': apellidos or 'NO_DETECTADO',
        'fecha_nacimiento': fecha or 'NO_DETECTADO',
        'imagen_path': ruta,
        'procesado_en': datetime.datetime.now().isoformat(),
    }

def _extraer_params_lab(texto):
    """Extrae parámetros numéricos de un informe de laboratorio."""
    pruebas = []
    alertas = []
    patron = re.compile(
        r'([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s\-\/\(\)]{2,40})\s*[:\s]\s*'
        r'([\d]+(?:[.,]\d+)?)\s*'
        r'([a-zA-Z\/\%\^µ]*)\s*'
        r'(\[?[HhLlAaBb]\]?)?\s*'
        r'(?:Ref(?:erencia)?[:\s]*([\d.,\s\-]+))?',
        re.MULTILINE
    )
    for m in patron.finditer(texto):
        nombre = m.group(1).strip()
        if len(nombre) < 3: continue
        try:
            valor = float(m.group(2).replace(',', '.'))
        except:
            continue
        unidad = (m.group(3) or '').strip()
        flag = (m.group(4) or '').strip().upper().replace('[','').replace(']','')
        referencia = (m.group(5) or '').strip()
        prueba = {
            'nombre': nombre,
            'valor': valor,
            'unidad': unidad,
            'tipo_dato': 'numerico',
            'flag': flag,
            'referencia': referencia,
        }
        pruebas.append(prueba)
        if flag in ('H', 'L', 'A', 'B'):
            tipo_alerta = 'ALTO [H]' if flag in ('H','A') else 'BAJO [L]'
            alertas.append({
                'prueba': nombre,
                'valor': valor,
                'unidad': unidad,
                'tipo': tipo_alerta,
                'referencia': referencia,
            })
    return pruebas, alertas

def procesar_imagen_lab(ruta, ciu_hint=''):
    """Procesa imagen de informe de laboratorio."""
    texto = _extraer_texto_imagen(ruta)
    if not texto:
        return None
    tipo = clasificar_documento(texto)
    pruebas, alertas = _extraer_params_lab(texto)
    return {
        'ciu_paciente': ciu_hint,
        'tipo_informe': tipo,
        'tipo_analisis': 'Análisis de Laboratorio',
        'pruebas': pruebas,
        'parametros_clinicos': pruebas,
        'alertas_detectadas': alertas,
        'campos_textuales': [],
        'rangos_referencia': [],
        'procesado_en': datetime.datetime.now().isoformat(),
    }

def _fmt_lab_resultado(lab_data, ciu=''):
    if not lab_data: return ''
    lineas = [f'Informe: {lab_data.get("tipo_analisis","")}']
    for p in lab_data.get('pruebas', []):
        flag = f' [{p.get("flag","")}]' if p.get('flag') else ''
        ref = f' (Ref: {p.get("referencia","")})' if p.get('referencia') else ''
        lineas.append(f'  • {p["nombre"]}: {p["valor"]} {p.get("unidad","")}{flag}{ref}')
    alertas = lab_data.get('alertas_detectadas', [])
    if alertas:
        lineas.append(f'Alertas ({len(alertas)}):')
        for a in alertas:
            lineas.append(f'  ⚠️  {a["tipo"]} {a["prueba"]}: {a["valor"]} {a.get("unidad","")}')
    return '\n'.join(lineas)

# ── Base de datos ─────────────────────────────────────────────────────────────

def cargar_bd():
    global _BD
    try:
        if os.path.exists(DB_JSON_PATH):
            with open(DB_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _BD = data.get('pacientes', data) if isinstance(data, dict) else {}
            print(f'BD cargada: {len(_BD)} pacientes')
    except Exception as e:
        print(f'Error cargando BD: {e}')
        _BD = {}

def guardar_bd():
    try:
        os.makedirs(DB_FOLDER, exist_ok=True)
        with open(DB_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump({'pacientes': _BD}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'Error guardando BD: {e}')

def registrar_paciente(ciu, dni_data=None, lab_data=None):
    """
    Crea o actualiza el registro de un paciente en la BD en memoria,
    y persiste el cambio a disco (JSON).

    ciu       : código único del paciente (CIU), siempre en mayúsculas.
    dni_data  : dict devuelto por procesar_imagen_dni (puede ser None).
    lab_data  : dict devuelto por procesar_imagen_lab (puede ser None).

    Si el paciente ya existe, se actualizan los campos provistos sin
    borrar los que ya tenía (ej: agregar un lab nuevo sin perder el DNI).
    Retorna el registro completo ya guardado.
    """
    ciu = str(ciu).upper().strip()
    if not ciu:
        raise ValueError('CIU vacío: no se puede registrar el paciente')

    registro = _BD.get(ciu, {
        'ciu': ciu,
        'datos_personales': {},
        'informe_laboratorio': None,
        'historial_laboratorio': [],
        'alertas_clinicas': [],
        'creado_en': datetime.datetime.now().isoformat(),
    })

    if dni_data:
        registro['datos_personales'] = {
            'nombres': dni_data.get('nombres', ''),
            'apellidos': dni_data.get('apellidos', ''),
            'fecha_nacimiento': dni_data.get('fecha_nacimiento', ''),
            'tipo_dni': dni_data.get('tipo_dni', ''),
        }

    if lab_data:
        registro['informe_laboratorio'] = lab_data
        registro['historial_laboratorio'].append(lab_data)
        nuevas_alertas = lab_data.get('alertas_detectadas', [])
        if nuevas_alertas:
            registro['alertas_clinicas'].extend(nuevas_alertas)

    registro['actualizado_en'] = datetime.datetime.now().isoformat()

    _BD[ciu] = registro
    guardar_bd()
    return registro


def listar_pacientes():
    """Retorna un resumen liviano de todos los pacientes en la BD."""
    resultado = []
    for ciu, reg in _BD.items():
        dp = reg.get('datos_personales', {})
        resultado.append({
            'ciu': ciu,
            'nombres': dp.get('nombres', ''),
            'apellidos': dp.get('apellidos', ''),
            'tiene_laboratorio': reg.get('informe_laboratorio') is not None,
            'num_alertas': len(reg.get('alertas_clinicas', [])),
        })
    return resultado


def listar_alertas():
    """Retorna todos los pacientes que tienen al menos una alerta clínica."""
    resultado = []
    for ciu, reg in _BD.items():
        alertas = reg.get('alertas_clinicas', [])
        if alertas:
            dp = reg.get('datos_personales', {})
            resultado.append({
                'ciu': ciu,
                'nombres': dp.get('nombres', ''),
                'apellidos': dp.get('apellidos', ''),
                'alertas': alertas,
            })
    return resultado


# Cargar BD al importar
cargar_bd()
print('aldimi_web.py cargado correctamente')