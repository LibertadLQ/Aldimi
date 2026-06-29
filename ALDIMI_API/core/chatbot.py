import re
import time
import logging

try:
    import nltk
    from nltk.corpus import stopwords as _sw_corpus
    from nltk.tokenize import word_tokenize as _wt
    _NLTK_OK = True
except Exception:
    _NLTK_OK = False

# Stopwords minimal en español
_STOPWORDS_ES = {
    'de','la','que','el','en','y','a','los','del','se','las','por','un','para',
    'con','no','una','su','al','lo','como','más','pero','sus','le','ya','o',
    'este','sí','porque','esta','entre','cuando','muy','sin','sobre','también',
    'me','hasta','hay','donde','quien','desde','nos','uno','mi','qué','ser',
    'es','si','te','tiene',
}

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
        '   Hospedaje gratuito para paciente y un acompañante.\n'
        '   Alimentación: desayuno, almuerzo y cena.\n'
        '   Apoyo psicosocial y consejería.\n'
        '   Gestión de citas médicas en hospitales de referencia.\n'
        '   Lavandería 2 veces por semana.\n'
        '   Acceso a internet y sala de esparcimiento.'
    ),
    'REQUISITOS': (
        'Requisitos para ingresar al Albergue ALDIMI:\n'
        '   Diagnóstico oncológico confirmado (informe médico).\n'
        '   DNI original del paciente y acompañante.\n'
        '   Carta de referencia del hospital tratante.\n'
        '   No contar con familiares en Lima que brinden alojamiento.\n'
        '   Llenar formulario de admisión al ingreso.'
    ),
    'VISITAS': (
        'Política de visitas del Albergue ALDIMI:\n'
        '   • Solo familiares directos (máx. 2 personas simultáneas).\n'
        '   • Horario: sábados 3pm-5pm.\n'
        '   • Niños menores de 12 años no ingresan a habitaciones.\n'
        '   • Toda visita debe registrarse en recepción con DNI.'
    ),
    'FALLBACK': (
        'No pude entender su consulta. Puede escribir:\n'
        '   horario | registro | donaciones | expedientes\n'
        '   alertas | reglamento | servicios | requisitos | visitas'
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
        'Guardia médica disponible 24 horas ante emergencias. '
        'Se lleva historial clínico completo en el sistema ALDIMI.'
    ),
    r'(prohib|no.permit|regla|norma)': (
        'PROHIBICIONES en el albergue:\n'
        '   Sustancias tóxicas o alcohol\n'
        '   Violencia física o verbal\n'
        '   Salidas no autorizadas\n'
        '   Visitas no coordinadas\n'
        '   Ruido después de las 10pm'
    ),
    r'(donar|donacion|ayudar|contribuir|apoyo)': 'Ver canales de donación en DONACION.',
    r'(horario|hora|cuando.atiende|abierto)': 'Ver horarios en HORARIO.',
}

INTENT_KEYWORDS = {
    'HORARIO'   : ['horario','hora','visita','apertura','cierre','cuando','abren','atienden'],
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

SYSTEM_METRICS = {
    'nlp': {'total': 0, 'reconocidos': 0, 'fallbacks': 0, 'tiempo_ms': 0.0,
            'por_intencion': {k: {'total':0,'correctos':0} for k in ['HORARIO','ADMISION','DONACION','EXPEDIENTE','ALERTA','EMOCIONAL']}},
}


def _get_sw():
    if _NLTK_OK:
        try:
            return set(_sw_corpus.words('spanish'))
        except Exception:
            pass
    return _STOPWORDS_ES


def _tokenize(text):
    if _NLTK_OK:
        try:
            return _wt(text.lower(), language='spanish')
        except Exception:
            pass
    return re.findall(r'\b[a-záéíóúüñ]{2,}\b', text.lower())


def _hash_pw(pw):
    # esta función se mantiene en users.py pero la dejamos aquí como helper si se usa
    import hashlib
    return hashlib.sha256(pw.encode()).hexdigest()


def _verify_pw(pw, hashed):
    import hashlib
    return hashlib.sha256(pw.encode()).hexdigest() == hashed


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
    if not tokens or not kws:
        return 0.0
    trans = str.maketrans('áéíóúüñ', 'aeiooun')
    kn = [k.translate(trans) for k in kws]
    hits = sum(1 for t in tokens if any(k in t or t in k for k in kn))
    if hits == 0:
        return 0.0
    base = {1: 0.80, 2: 0.90}.get(hits, 0.95)
    if len(tokens) <= 3:
        base = min(base + 0.05, 1.0)
    return round(base, 3)


def analizar_sentimiento(texto):
    if not texto:
        return {'score': 0.0, 'etiqueta': 'NEUTRO', 'palabras_neg': [], 'palabras_pos': []}
    tokens = re.findall(r'\b[a-z]{3,}\b', str(texto).lower())
    hits_neg = [t for t in tokens if t in NEGATIVE_WORDS]
    hits_pos = [t for t in tokens if t in POSITIVE_WORDS]
    if not tokens:
        return {'score': 0.0, 'etiqueta': 'NEUTRO', 'palabras_neg': [], 'palabras_pos': []}
    score = (len(hits_pos) - len(hits_neg)) / max(len(tokens), 1)
    score = max(-1.0, min(1.0, score * 10))
    etiqueta = 'NEGATIVO' if score < -0.1 else ('POSITIVO' if score > 0.1 else 'NEUTRO')
    return {'score': round(score, 3), 'etiqueta': etiqueta, 'palabras_neg': list(set(hits_neg)), 'palabras_pos': list(set(hits_pos))}


def _sentiment_neg_score(tokens):
    if not tokens:
        return 0.0
    trans = str.maketrans('áéíóúüñ', 'aeiooun')
    neg = {w.translate(trans) for w in NEGATIVE_WORDS}
    h = sum(1 for t in tokens if t in neg)
    return -(h / len(tokens))


def buscar_faq_reglamento(msg):
    msg_norm = str(msg).lower()
    msg_norm = re.sub(r'[aeiouáéíóúüñ]', '.', msg_norm)
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
        elapsed = round((time.time() - t0) * 1000, 2)
        SYSTEM_METRICS['nlp']['total'] += 1
        SYSTEM_METRICS['nlp']['reconocidos'] += 1
        SYSTEM_METRICS['nlp']['tiempo_ms'] += elapsed
        if 'REGLAMENTO' in SYSTEM_METRICS['nlp']['por_intencion']:
            SYSTEM_METRICS['nlp']['por_intencion']['REGLAMENTO']['total'] += 1
            SYSTEM_METRICS['nlp']['por_intencion']['REGLAMENTO']['correctos'] += 1
        return 'REGLAMENTO', 0.95, faq
    intent, conf = detect_intent(msg)
    elapsed = round((time.time() - t0) * 1000, 2)
    SYSTEM_METRICS['nlp']['total'] += 1
    SYSTEM_METRICS['nlp']['tiempo_ms'] += elapsed
    if intent != 'FALLBACK':
        SYSTEM_METRICS['nlp']['reconocidos'] += 1
        if intent in SYSTEM_METRICS['nlp']['por_intencion']:
            SYSTEM_METRICS['nlp']['por_intencion'][intent]['total'] += 1
            SYSTEM_METRICS['nlp']['por_intencion'][intent]['correctos'] += 1
    else:
        SYSTEM_METRICS['nlp']['fallbacks'] += 1
    resp = KNOWLEDGE_BASE.get(intent, KNOWLEDGE_BASE['FALLBACK'])
    return intent, conf, resp


def detect_risk_language(text):
    risk_kw = [
        'suicidio','morir','no quiero vivir','desesperado','sin salida',
        'hacerme daño','lastimarme','no sirvo','crisis',
    ]
    return any(k in str(text).lower() for k in risk_kw)
