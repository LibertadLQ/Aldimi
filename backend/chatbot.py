from __future__ import annotations
 
import difflib
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
 
from .db import cargar_bd, cargar_sesiones
from .alertas import filtrar_alertas_criticas
from .patient_nlp import get_nlp
 
 
# ═══════════════════════════════════════════════════════════════════════
# 1. UTILIDADES DE TEXTO
# ═══════════════════════════════════════════════════════════════════════
 
def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes, sin signos de puntuación, espacios colapsados."""
    if not texto:
        return ""
    t = texto.strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9ñ\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
 
 
def _similitud(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()
 
 
def coincide_variante(texto_norm: str, variantes: List[str], umbral: float = 0.80) -> bool:
    """
    True si `texto_norm` contiene alguna variante tal cual, o si es lo
    bastante parecido a alguna (tolera errores de tipeo / reformulaciones
    cortas), usando similitud de secuencia sobre frases completas y sobre
    cada palabra del mensaje comparada contra cada variante.
    """
    if not texto_norm:
        return False
 
    for variante in variantes:
        v = normalizar_texto(variante)
        if not v:
            continue
        # Coincidencia directa, pero respetando límites de palabra:
        # así "si" no matchea dentro de "requiSItos", y "no" no matchea
        # dentro de "doNacion", etc.
        if re.search(rf"\b{re.escape(v)}\b", texto_norm):
            return True
        # Similitud global de la frase completa
        if _similitud(texto_norm, v) >= umbral:
            return True
        # Similitud contra cada "ventana" de palabras del mensaje del
        # mismo tamaño que la variante (para frases cortas tipo "sí", "ok")
        palabras_msg = texto_norm.split()
        palabras_var = v.split()
        n = len(palabras_var)
        if n <= len(palabras_msg):
            for i in range(len(palabras_msg) - n + 1):
                ventana = " ".join(palabras_msg[i:i + n])
                if _similitud(ventana, v) >= umbral:
                    return True
    return False
 
 
# ═══════════════════════════════════════════════════════════════════════
# 2. RESPUESTAS CORTAS DE CONTEXTO (sí / no / gracias / saludo / despedida)
# ═══════════════════════════════════════════════════════════════════════
 
_VARIANTES_AFIRMACION = [
    "si", "sí", "claro", "ok", "okay", "dale", "de acuerdo", "por favor",
    "obvio", "asi es", "correcto", "afirmativo", "va", "vale", "eso quiero",
    "quiero mas informacion", "cuentame mas", "sigue", "pues si", "pues claro",
    "por supuesto", "seguro", "listo", "esta bien", "ya", "sip", "dale pues",
]

_VARIANTES_NEGACION = [
    "no", "no gracias", "nada mas", "eso es todo", "asi esta bien",
    "no por ahora", "negativo", "esta bien asi", "ninguna", "no necesito nada mas",
    "ah no", "no pues", "mejor despues", "ya no", "creo que no", "quizas despues",
]
 
_VARIANTES_AGRADECIMIENTO = [
    "gracias", "muchas gracias", "mil gracias", "muy amable",
    "te agradezco", "gracias por la ayuda", "gracias por todo",
    "gracias hermano", "gracias amigo", "gracias bro",
]
 
_VARIANTES_SALUDO = [
    "hola", "buenas", "buenos dias", "buenas tardes", "buenas noches",
    "que tal", "hey", "saludos",
]
 
_VARIANTES_DESPEDIDA = [
    "adios", "chau", "hasta luego", "nos vemos", "me voy", "bye",
]
 
 
def es_afirmacion(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_AFIRMACION, umbral=0.85)
 
 
def es_negacion(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_NEGACION, umbral=0.85)
 
 
def es_agradecimiento(texto_norm: str) -> bool:
    if es_negacion(texto_norm):
        return False
    return coincide_variante(texto_norm, _VARIANTES_AGRADECIMIENTO, umbral=0.75)
 
 
def es_saludo(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_SALUDO, umbral=0.85)
 
 
def es_despedida(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_DESPEDIDA, umbral=0.85)
 

def es_ciu_valido(texto: str) -> bool:
    """Valida formatos comunes de CIU/DNI: 8 dígitos Perú o 1-2 letras + 5-7 dígitos."""
    if not texto:
        return False
    t = texto.strip().upper()
    return bool(re.fullmatch(r"\d{8}", t) or re.fullmatch(r"[A-Z]{1,2}\d{5,7}", t))


def _normalizar_ciu(ciu: str) -> str:
    if not ciu:
        return ""
    ciu = ciu.strip().upper()
    if re.fullmatch(r"[A-Z]{1,2}\d{5,7}", ciu):
        return re.sub(r"[A-Z]", "", ciu)
    return ciu


def _buscar_registro_por_ciu(bd: Dict[str, Any], ciu: str) -> Optional[Dict[str, Any]]:
    if not ciu:
        return None
    ciu_raw = ciu.strip().upper()
    ciu_norm = _normalizar_ciu(ciu_raw)

    if ciu_raw in bd:
        return bd[ciu_raw]
    if ciu_norm and ciu_norm != ciu_raw and ciu_norm in bd:
        return bd[ciu_norm]

    for key, registro in bd.items():
        if _normalizar_ciu(key) == ciu_norm:
            return registro
    return None


def _campo_a_texto(valor: Any) -> str:
    if valor is None:
        return "NO_DETECTADO"
    if isinstance(valor, str):
        texto = valor.strip()
        return texto if texto else "NO_DETECTADO"
    return str(valor).strip() or "NO_DETECTADO"


def _extraer_datos_personales_desde_campos(campos: Optional[Dict[str, Any]], ciu: Optional[str] = None) -> Dict[str, Any]:
    campos = campos or {}
    nombres = _campo_a_texto(
        campos.get("nombres") or campos.get("nombre") or campos.get("first_name")
        or campos.get("given_name") or campos.get("nombre_completo") or campos.get("full_name")
        or campos.get("name")
    )
    apellidos = _campo_a_texto(
        campos.get("apellidos") or campos.get("apellido") or campos.get("last_name")
        or campos.get("family_name")
    )

    if apellidos == "NO_DETECTADO":
        paterno = _campo_a_texto(campos.get("apellido_paterno") or campos.get("apellido1"))
        materno = _campo_a_texto(campos.get("apellido_materno") or campos.get("apellido2"))
        if paterno != "NO_DETECTADO" or materno != "NO_DETECTADO":
            apellidos = " ".join(
                p for p in [paterno, materno] if p != "NO_DETECTADO"
            ) or "NO_DETECTADO"

    if nombres == "NO_DETECTADO" and apellidos != "NO_DETECTADO":
        # Algunas fuentes pueden devolver el nombre completo en un solo campo.
        nombre_completo = _campo_a_texto(campos.get("nombre_completo") or campos.get("full_name") or campos.get("name"))
        if nombre_completo != "NO_DETECTADO" and " " in nombre_completo:
            partes = nombre_completo.split()
            nombres = " ".join(partes[:-1])
            if apellidos == "NO_DETECTADO":
                apellidos = partes[-1]

    if nombres == "NO_DETECTADO" and apellidos != "NO_DETECTADO" and " " in apellidos:
        partes = apellidos.split()
        if len(partes) > 1:
            apellidos = partes[-1]
            nombres = " ".join(partes[:-1])

    fecha = _campo_a_texto(
        campos.get("fecha_nacimiento") or campos.get("fecha") or campos.get("fecha_nac")
        or campos.get("dob") or campos.get("birth_date")
    )

    ciu_text = _normalizar_ciu(
        str(campos.get("ciu") or campos.get("dni") or "")
    )
    if not ciu_text and ciu:
        ciu_text = _normalizar_ciu(ciu)

    return {
        "ciu": ciu_text,
        "nombres": nombres,
        "apellidos": apellidos,
        "fecha_nacimiento": fecha,
    }


def _datos_validos(entrada: Any) -> bool:
    return bool(entrada and isinstance(entrada, str) and entrada.strip()
                and entrada.strip() != "NO_DETECTADO")


def _extraer_datos_personales_desde_sesiones(ciu: str) -> Dict[str, Any]:
    ciu_norm = _normalizar_ciu(ciu)
    if not ciu_norm:
        return {}

    sesiones = cargar_sesiones()
    for sesion in reversed(sesiones):
        if sesion.get("tipo_documento") not in {"DNI_PERU", "DNI_USA"}:
            continue
        campos = sesion.get("campos", {}) or {}
        if _normalizar_ciu(str(campos.get("ciu", ""))) != ciu_norm:
            continue
        datos = _extraer_datos_personales_desde_campos(campos, ciu_norm)
        if datos:
            return datos
    return {}


def _extraer_datos_personales_desde_registro(registro: Dict[str, Any], ciu: Optional[str] = None) -> Dict[str, Any]:
    datos = registro.get("datos_personales", {}) or {}
    resultado = {
        "ciu": _normalizar_ciu(str(datos.get("ciu", "") or registro.get("ciu", "") or "")) or _normalizar_ciu(ciu or ""),
        "nombres": _campo_a_texto(datos.get("nombres")),
        "apellidos": _campo_a_texto(datos.get("apellidos")),
        "fecha_nacimiento": _campo_a_texto(datos.get("fecha_nacimiento")),
    }

    # Completar con los mejores datos encontrados en los DNI guardados.
    documentos = registro.get("documentos_ocr", []) or []
    mejor_doc: Dict[str, Any] = {}
    mejor_puntaje = -1
    mejor_timestamp = ""

    for doc in documentos:
        if doc.get("tipo_documento") not in {"DNI_PERU", "DNI_USA"}:
            continue
        doc_datos = _extraer_datos_personales_desde_campos(doc.get("campos", {}) or {}, resultado["ciu"] or ciu)
        puntaje = sum(
            1 for campo in ("nombres", "apellidos", "fecha_nacimiento")
            if _datos_validos(doc_datos.get(campo))
        )
        timestamp = str(doc.get("timestamp", ""))
        if puntaje > mejor_puntaje or (puntaje == mejor_puntaje and timestamp > mejor_timestamp):
            mejor_doc = doc_datos
            mejor_puntaje = puntaje
            mejor_timestamp = timestamp

    if mejor_doc:
        for campo in ("ciu", "nombres", "apellidos", "fecha_nacimiento"):
            if not _datos_validos(resultado.get(campo)) and _datos_validos(mejor_doc.get(campo)):
                resultado[campo] = mejor_doc[campo]

    if not all(_datos_validos(resultado.get(campo)) for campo in ("nombres", "apellidos", "fecha_nacimiento")):
        datos_sesiones = _extraer_datos_personales_desde_sesiones(resultado["ciu"] or ciu or "")
        for campo in ("ciu", "nombres", "apellidos", "fecha_nacimiento"):
            if not _datos_validos(resultado.get(campo)) and _datos_validos(datos_sesiones.get(campo)):
                resultado[campo] = datos_sesiones[campo]

    return resultado


# ═══════════════════════════════════════════════════════════════════════
# 3. INTENCIONES (varias formas de decir lo mismo, no solo una palabra)
# ═══════════════════════════════════════════════════════════════════════
 
INTENCIONES: Dict[str, List[str]] = {
    "horario": [
        "horario de atencion", "a que hora atienden", "cuando atienden",
        "horario del albergue", "que horario tienen", "estan abiertos",
        "a que hora abren", "a que hora cierran", "horario",
    ],
    "donacion": [
        "donaciones", "donacion", "como puedo donar", "quiero donar",
        "aceptan donaciones", "donativos", "ayudar economicamente",
        "hacer una donacion",
    ],
    "admision": [
        "registrar paciente", "quiero registrar", "nuevo paciente",
        "dar de alta", "agregar paciente", "registro de paciente",
        "inscribir paciente", "registro",
    ],
    "expediente": [
        "expediente", "expedientes", "ver expediente", "ver expedientes",
        "consultar expediente", "consultar expedientes", "historial clinico",
        "historia clinica", "historial medico", "historico medico",
        "ficha clinica", "ficha del paciente", "mi expediente", "mi historial",
        "informacion del paciente", "datos del paciente",
    ],
    "evolucion": [
        "como estoy", "como voy", "como voy en mi proceso",
        "como crees que voy", "que debo hacer", "que hago", "que deberia hacer",
        "debo mejorar", "estoy mejorando", "como estoy de salud",
        "mi proceso", "mi evolucion", "que me recomiendas",
        "consejos para mejorar", "que cuidados debo tener",
    ],
    "alertas_clinicas": [
        "alertas clinicas", "alertas activas", "hay alguna alerta",
        "valores alterados", "resultados anormales", "algo fuera de rango",
    ],
    "REGLAMENTO": [
        "reglamento", "reglamento interno", "normas del albergue",
        "reglas de la casa", "politicas del albergue",
    ],
    "SERVICIOS": [
        "servicios disponibles", "que servicios tienen", "que ofrecen",
        "que servicios brindan", "servicios del albergue", "servicios",
    ],
    "REQUISITOS": [
        "requisitos de admision", "como ingreso", "que necesito para ingresar",
        "requisitos para admitir", "condiciones de ingreso",
        "requisitos de admision de pacientes", "requisitos",
    ],
    "VISITAS": [
        "horario de visita", "horarios de visita", "cuando puedo visitar",
        "puedo visitar", "dia de visita", "hora de visita", "visitas",
    ],
    "pronostico_salud": [
        "que me pasara", "que me pasará", "estare bien", "estaré bien",
        "me voy a curar", "me voy a morir", "que futuro tengo", "que pasara conmigo",
        "que me pasará con mi salud", "tengo miedo de no sanar", "que va a pasar"
    ],
    "contexto_historial": [
        "como saben eso", "como saben mi historial", "como saben que paso",
        "como saben lo que tengo", "como saben mi informacion", "de donde sacan mis datos"
    ],
    "cuidados_recomendaciones": [
        "que debo cuidar", "que debo tener en cuenta", "que cuidados debo tener",
        "que me recomiendas hacer", "consejos para mi salud", "que cuidados"
    ],
    "contencion_emocional": [
        "tengo miedo", "estoy asustado", "no se que hacer", "no aguanto",
        "estoy angustiado", "estoy triste", "me siento mal anímicamente"
    ],
    "pregunta_otro_usuario": [
        "como esta", "como está", "como se siente", "como es su salud", "cual es su salud",
        "como va", "como esta esa persona", "que tal su salud", "como esta ella", "como esta el",
        "como estan", "informacion de otro", "otro paciente", "como le va"
    ],
}
 
# Preguntas de cierre que dispara el bot luego de responder una intención
# informativa; se guardan en el contexto para interpretar la respuesta corta
# del usuario en el siguiente mensaje.
PREGUNTA_OTRO_SERVICIO = "¿Deseas información sobre algún otro servicio?"
 
 
# ── 3-bis. Detección de riesgo emocional (ALERTA) ──
# Lista corta y ampliable de frases que sugieren angustia o riesgo
# emocional. Esto NO es una herramienta de diagnóstico ni de clasificación
# clínica: es únicamente un disparador para escalar el caso a una persona
# del equipo de soporte psicosocial. El equipo clínico de ALDIMI debería
# revisar y ampliar esta lista según su criterio.
_VARIANTES_RIESGO_EMOCIONAL = [
    "quiero morir", "no quiero vivir", "no tengo ganas de vivir",
    "quiero hacerme daño", "me quiero hacer daño", "no aguanto mas",
    "ya no puedo mas", "quiero desaparecer", "no vale la pena seguir",
    "quiero terminar con todo", "me quiero morir",
]
 
 
def es_riesgo_emocional(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_RIESGO_EMOCIONAL, umbral=0.82)


# ── Detección de emergencia física (sangrado, fiebre alta, dolor intenso, etc.) ──
_VARIANTES_EMERGENCIA_SINTOMAS = [
    "sangrando", "estoy sangrando", "sangra", "sangrado",
    "fiebre alta", "tengo fiebre", "fiebre", "dolor insoportable",
    "dolor muy fuerte", "no puedo respirar", "dificultad para respirar",
    "desmaye", "me desmaye", "me desmayé", "vomito sangre", "vomito con sangre",
]


def es_emergencia_fisica(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_EMERGENCIA_SINTOMAS, umbral=0.78)


def registrar_alerta_fisica(ciu: Optional[str], mensaje_original: str) -> None:
    """
    Registro simple de una alerta física para que el equipo de turno la atienda.
    Implementar integración real (guardar en BD, notificación por Slack/telefono)
    según el procedimiento operativo del albergue.
    """
    print(
        f"[ALDIMI][ALERTA-FISICA] ciu={ciu or 'sin_ciu'} mensaje={mensaje_original!r} "
        f"timestamp={datetime.now().isoformat()}"
    )
 
 
def registrar_alerta_riesgo(ciu: Optional[str], mensaje_original: str) -> None:
    """
    Punto de enganche para notificar al equipo de soporte psicosocial.
 
    TODO: aquí falta la integración real (guardar en ALDIMI_DB, avisar por
    correo/Slack al equipo, etc.). Por ahora solo deja constancia en logs
    para que no se pierda el caso mientras se define el canal real.
    """
    print(
        f"[ALDIMI][ALERTA-RIESGO] ciu={ciu or 'sin_ciu'} "
        f"mensaje={mensaje_original!r} timestamp={datetime.now().isoformat()}"
    )
 
 
def detectar_intencion(texto_norm: str) -> Optional[str]:
    """
    Devuelve la intención con mejor coincidencia, o None si nada supera
    un umbral mínimo razonable. No depende de una palabra exacta: usa
    `coincide_variante`, que tolera reformulaciones y errores de tipeo.
    """
    mejor_intencion = None
    mejor_score = 0.0
 
    for intencion, variantes in INTENCIONES.items():
        for variante in variantes:
            v = normalizar_texto(variante)
            score = _similitud(texto_norm, v)
            if re.search(rf"\b{re.escape(v)}\b", texto_norm):
                score = max(score, 0.95)
            if score > mejor_score:
                mejor_score = score
                mejor_intencion = intencion
 
    if mejor_score >= 0.55:
        return mejor_intencion
    return None
 
 
# ═══════════════════════════════════════════════════════════════════════
# 4. CONTENIDO INFORMATIVO — REEMPLAZAR CON EL TEXTO REAL DE ALDIMI
# ═══════════════════════════════════════════════════════════════════════
# NOTA: estos textos son placeholders de ejemplo. Sustitúyelos por el
# contenido real que ya manejabas (horarios, reglamento, requisitos, etc.)
# No es información verificada del albergue ALDIMI.
 
RESPUESTAS_INFORMATIVAS: Dict[str, str] = {
    "horario": (
        "El horario de atención del Albergue ALDIMI es:\n"
        "   Lunes a Sábado: 9:00 a.m. a 6:00 p.m.\n"
        "   Domingos y feriados: CERRADO.\n"
        "   Urgencias: número de guardia 24/7."
    ),
    "admision": (
        "Para registrar a un paciente necesita:\n"
        "   1. Código CIU del DNI del paciente.\n"
        "   2. Imagen del documento de identidad (PNG/JPG).\n"
        "   El sistema extraerá los datos con OCR + CNN automáticamente.\n"
        "Escriba REGISTRO para iniciar el proceso."
    ),
    "donacion": (
        "Canales de donación del Albergue ALDIMI:\n"
        "   • Yape / Plin: 999-888-777\n"
        "   • BCP: Cuenta 123-456789-0-12\n"
        "   • Interbank: 200-3456789-012\n"
        "   • En especie: Ropa, alimentos, medicamentos (lunes a sábado 9am-5pm).\n"
        "   • Voluntariado: coordinacion@aldimi.org"
    ),
    "expediente": (
        "Para consultar el expediente, indique el CIU del paciente.\n"
        "   Formato Perú: 8 dígitos (ej: 42951703)\n"
        "   Formato USA : letra + 6 dígitos (ej: W839927)\n"
        "Podrá ver: datos personales, análisis clínicos y alertas detectadas."
    ),
    "REGLAMENTO": (
        "Reglamento del Albergue ALDIMI:\n"
        "   ADMISIÓN: Solo pacientes oncológicos con referencia médica válida.\n"
        "   PERMANENCIA: Máxima 30 días prorrogables según evaluación médica.\n"
        "   HORARIO silencio: 10pm-6am.\n"
        "   ALIMENTACIÓN: desayuno, almuerzo y cena incluidos.\n"
        "   PROHIBIDO: alcohol, cigarrillos, visitas no autorizadas.\n"
        "   VISITAS: Solo familiares directos, sábados 3pm-5pm."
    ),
    "SERVICIOS": (
        "Servicios del Albergue ALDIMI:\n"
        "   Hospedaje gratuito para paciente y un acompañante.\n"
        "   Alimentación: desayuno, almuerzo y cena.\n"
        "   Apoyo psicosocial y consejería.\n"
        "   Gestión de citas médicas en hospitales de referencia.\n"
        "   Lavandería 2 veces por semana.\n"
        "   Acceso a internet y sala de esparcimiento."
    ),
    "REQUISITOS": (
        "Requisitos para ingresar al Albergue ALDIMI:\n"
        "   Diagnóstico oncológico confirmado (informe médico).\n"
        "   DNI original del paciente y acompañante.\n"
        "   Carta de referencia del hospital tratante.\n"
        "   No contar con familiares en Lima que brinden alojamiento.\n"
        "   Llenar formulario de admisión al ingreso."
    ),
    "VISITAS": (
        "Política de visitas del Albergue ALDIMI:\n"
        "   • Solo familiares directos (máx. 2 personas simultáneas).\n"
        "   • Horario: sábados 3pm-5pm.\n"
        "   • Niños menores de 12 años no ingresan a habitaciones.\n"
        "   • Toda visita debe registrarse en recepción con DNI."
    ),
}
 
# Respuesta de fallback cuando no se reconoce ninguna intención.
RESPUESTA_FALLBACK = (
    "No pude entender su consulta. Puede escribir:\n"
    "   horario | registro | donaciones | expedientes | como estoy\n"
    "   alertas | reglamento | servicios | requisitos | visitas"
)
 
# Respuesta cuando se detecta una posible situación de riesgo emocional
# (ver sección 3-bis, es prioritaria sobre cualquier otra intención).
RESPUESTA_ALERTA_RIESGO = (
    "Se ha detectado una situación de riesgo emocional.\n"
    "Se registrará una alerta para el equipo de soporte psicosocial.\n"
    "El personal evaluará el caso a la brevedad.\n"
    "En emergencias llame al número de guardia 24/7."
)
 
 
# ═══════════════════════════════════════════════════════════════════════
# 5. CONTEXTO CONVERSACIONAL (memoria de la última pregunta)
# ═══════════════════════════════════════════════════════════════════════
# Se guarda en memoria del proceso, indexado por CIU cuando existe, o bajo
# una llave genérica cuando la conversación aún no tiene un CIU asociado.
# Si en el futuro corres varias instancias del backend (multi-proceso),
# esto debería migrar a algo compartido (Redis, la propia BD, etc.), pero
# para el uso actual (un solo backend local) alcanza con un dict.
 
_CONTEXTOS: Dict[str, Dict[str, Any]] = {}
_LLAVE_SIN_CIU = "_sin_ciu_"
 
 
def _llave_contexto(ciu: Optional[str]) -> str:
    return ciu.strip().upper() if ciu else _LLAVE_SIN_CIU
 
 
def _obtener_contexto(ciu: Optional[str]) -> Dict[str, Any]:
    llave = _llave_contexto(ciu)
    return _CONTEXTOS.setdefault(llave, {"esperando": None, "ultima_intencion": None})
 
 
def _actualizar_contexto(ciu: Optional[str], **kwargs) -> None:
    ctx = _obtener_contexto(ciu)
    ctx.update(kwargs)
 
 
def _limpiar_espera(ciu: Optional[str]) -> None:
    _actualizar_contexto(ciu, esperando=None)
 
 
# ═══════════════════════════════════════════════════════════════════════
# 6. EVOLUCIÓN DEL PACIENTE Y RECOMENDACIONES
# ═══════════════════════════════════════════════════════════════════════
 
def _informes_ordenados(registro: Dict[str, Any]) -> List[Dict[str, Any]]:
    informes = registro.get("informes_laboratorio", []) or []
    # Solo consideramos informes que realmente trajeron pruebas legibles.
    con_datos = [inf for inf in informes if inf.get("pruebas")]
    con_datos.sort(key=lambda inf: inf.get("registrado_en", ""))
    return con_datos
 
 
def resumen_evolucion(registro: Dict[str, Any]) -> Tuple[str, str]:
    """
    Compara el primer y el último informe de laboratorio con datos y
    devuelve (etiqueta, explicacion). etiqueta ∈
    {"favorable", "estable", "desfavorable", "sin_datos_suficientes"}.
    """
    informes = _informes_ordenados(registro)
 
    if len(informes) < 2:
        return (
            "sin_datos_suficientes",
            "Aún no hay suficientes informes de laboratorio registrados "
            "para comparar la evolución del paciente.",
        )
 
    primero, ultimo = informes[0], informes[-1]
    alertas_antes = len(primero.get("alertas_detectadas", []) or [])
    alertas_ahora = len(ultimo.get("alertas_detectadas", []) or [])
 
    # Comparación fina: pruebas que aparecen en ambos informes y si su
    # flag (H/L/normal) mejoró o empeoró.
    pruebas_antes = {p.get("nombre"): p.get("flag") for p in (primero.get("pruebas") or [])}
    pruebas_ahora = {p.get("nombre"): p.get("flag") for p in (ultimo.get("pruebas") or [])}
 
    mejoras, empeoras = [], []
    for nombre, flag_ahora in pruebas_ahora.items():
        if nombre not in pruebas_antes:
            continue
        flag_antes = pruebas_antes[nombre]
        estaba_alterado = flag_antes in ("H", "L")
        esta_alterado = flag_ahora in ("H", "L")
        if estaba_alterado and not esta_alterado:
            mejoras.append(nombre)
        elif not estaba_alterado and esta_alterado:
            empeoras.append(nombre)
 
    if alertas_ahora < alertas_antes or (mejoras and not empeoras):
        etiqueta = "favorable"
    elif alertas_ahora > alertas_antes or (empeoras and not mejoras):
        etiqueta = "desfavorable"
    else:
        etiqueta = "estable"
 
    partes = [
        f"Se compararon {len(informes)} informes de laboratorio "
        f"(del {primero.get('registrado_en', '')[:10]} al {ultimo.get('registrado_en', '')[:10]})."
    ]
    if mejoras:
        partes.append(f"Mejoraron: {', '.join(mejoras)}.")
    if empeoras:
        partes.append(f"Empeoraron: {', '.join(empeoras)}.")
    if not mejoras and not empeoras:
        partes.append("No se detectaron cambios relevantes en las pruebas comunes.")
 
    return etiqueta, " ".join(partes)
 
 
# Recomendaciones orientativas por tipo de prueba alterada. Son genéricas
# y de ejemplo: no reemplazan criterio médico. Amplía este diccionario
# según lo que realmente necesite el equipo clínico de ALDIMI.
_RECOMENDACIONES_POR_PRUEBA: Dict[str, str] = {
    "glucosa": "vigilar la alimentación y controlar niveles de glucosa periódicamente.",
    "hemoglobina": "evaluar signos de anemia y considerar reforzar la dieta con hierro.",
    "colesterol": "revisar hábitos alimenticios y actividad física.",
    "creatinina": "dar seguimiento a la función renal con el personal médico.",
    "leucocitos": "estar atentos a signos de infección y reportarlos al personal de salud.",
    "presion": "monitorear la presión arterial con mayor frecuencia.",
}
 
 
def generar_recomendaciones(registro: Dict[str, Any]) -> List[str]:
    """Recomendaciones básicas, orientativas, según alertas clínicas vigentes."""
    alertas = registro.get("alertas_clinicas", []) or []
    if not alertas:
        return []
 
    recomendaciones = []
    vistos = set()
    for alerta in alertas:
        nombre_prueba = str(alerta.get("prueba", "")).lower() if isinstance(alerta, dict) else ""
        encontrado = False
        for clave, texto in _RECOMENDACIONES_POR_PRUEBA.items():
            if clave in nombre_prueba and clave not in vistos:
                recomendaciones.append(f"• {alerta.get('prueba', clave).title()}: {texto}")
                vistos.add(clave)
                encontrado = True
                break
        if not encontrado and nombre_prueba and nombre_prueba not in vistos:
            recomendaciones.append(
                f"• {alerta.get('prueba', nombre_prueba).title()}: seguimiento con personal médico recomendado."
            )
            vistos.add(nombre_prueba)
 
    return recomendaciones


def construir_respuesta_expediente(registro: Dict[str, Any], compacto: bool = False) -> str:
    """
    Arma el mensaje completo del expediente: datos básicos + evolución + recomendaciones.
    
    Parámetros:
        registro: diccionario con datos del paciente
        compacto: si True, devuelve solo datos básicos
    
    Retorna: string formateado con la información del expediente
    """
    ciu = registro.get("ciu", "")
    datos = _extraer_datos_personales_desde_registro(registro, ciu)

    if compacto:
        lineas = [f"CIU: {ciu}"]
        if datos:
            nombres = datos.get("nombres", "NO_DETECTADO")
            apellidos = datos.get("apellidos", "NO_DETECTADO")
            lineas.append(f"Nombre: {apellidos} {nombres}".strip())
            lineas.append(f"Fecha nac.: {datos.get('fecha_nacimiento', 'NO_DETECTADO')}")
        return "\n".join(lineas)

    lineas = [f"Expediente {ciu}:"]
    if datos:
        nombres = datos.get("nombres", "NO_DETECTADO")
        apellidos = datos.get("apellidos", "NO_DETECTADO")
        lineas.append(f"• Paciente: {nombres} {apellidos}")

    etiqueta, explicacion = resumen_evolucion(registro)
    etiquetas_legibles = {
        "favorable": "Evolución favorable ✅",
        "estable": "Evolución estable ➖",
        "desfavorable": "Evolución desfavorable ⚠️",
        "sin_datos_suficientes": "Aún sin datos suficientes para evaluar evolución",
    }
    lineas.append(f"• {etiquetas_legibles[etiqueta]}")
    lineas.append(explicacion)

    recomendaciones = generar_recomendaciones(registro)
    if recomendaciones:
        lineas.append("Recomendaciones orientativas:")
        lineas.extend(recomendaciones)
        lineas.append(
            "Estas recomendaciones son informativas y no sustituyen la "
            "evaluación de un profesional de salud."
        )
    
    return "\n".join(lineas)


def construir_respuesta_salud_otro_usuario(registro: Dict[str, Any], ciu: str) -> str:
    """
    Construye una respuesta tranquilizadora/equilibrada sobre la salud de otra persona.
    Analiza alertas detectadas y NO detectadas para generar un mensaje que calme
    sin ocultar la información relevante.
    
    La estrategia es:
    1. Extraer datos personales.
    2. Obtener último informe y alertas.
    3. Listar lo que está BIEN (sin alertas).
    4. Listar lo que REQUIERE ATENCIÓN (con alertas).
    5. Redactar respuesta equilibrada y tranquilizadora.
    """
    datos = _extraer_datos_personales_desde_registro(registro, ciu)
    nombre_legible = f"{datos.get('nombres', 'Paciente')} {datos.get('apellidos', '')}".strip() if datos else "Paciente"
    
    informes = _informes_ordenados(registro)
    if not informes:
        return (
            f"Para {nombre_legible} (CIU {ciu}): Aún no hay informes de laboratorio registrados. "
            "El equipo médico evaluará al paciente próximamente."
        )
    
    ultimo_informe = informes[-1]
    pruebas = ultimo_informe.get("pruebas", []) or []
    fecha_informe = ultimo_informe.get("registrado_en", "fecha no disponible")[:10]
    
    # Separar pruebas normales de pruebas con alerta
    pruebas_normales = []
    pruebas_con_alerta = []
    
    for prueba in pruebas:
        nombre = prueba.get("nombre", "")
        flag = prueba.get("flag", "")
        if flag in ("H", "L"):  # Hay alerta
            tipo_alerta = "ALTO" if flag == "H" else "BAJO"
            pruebas_con_alerta.append((nombre, prueba.get("valor"), prueba.get("unidad"), tipo_alerta))
        elif nombre:  # Normal
            pruebas_normales.append((nombre, prueba.get("valor"), prueba.get("unidad")))
    
    # Construir respuesta equilibrada
    lineas = [
        f"📋 Informe de salud de {nombre_legible} (CIU {ciu}) - {fecha_informe}:",
        "",
    ]
    
    # Sección POSITIVA (lo que está bien)
    if pruebas_normales:
        lineas.append(f"✅ BIEN (sin alertas - {len(pruebas_normales)} parámetros normales):")
        for nombre, valor, unidad in pruebas_normales[:5]:  # Mostrar primeros 5
            valor_str = f"{valor} {unidad}" if unidad else str(valor)
            lineas.append(f"   • {nombre}: {valor_str}")
        if len(pruebas_normales) > 5:
            lineas.append(f"   ... y {len(pruebas_normales) - 5} más en rango normal.")
        lineas.append("")
    
    # Sección ALERTA (lo que requiere atención)
    if pruebas_con_alerta:
        lineas.append(f"⚠️  REQUIERE ATENCIÓN ({len(pruebas_con_alerta)} parámetro(s)):")
        for nombre, valor, unidad, tipo_alerta in pruebas_con_alerta:
            valor_str = f"{valor} {unidad}" if unidad else str(valor)
            icono = "⬆️" if tipo_alerta == "ALTO" else "⬇️"
            lineas.append(f"   {icono} {nombre}: {valor_str} ({tipo_alerta})")
        lineas.append("")
    else:
        lineas.append("✨ Todos los parámetros se encuentran dentro de rango normal. Buenas noticias.")
        lineas.append("")
    
    # Conclusión tranquilizadora
    nombre_corto = nombre_legible.split()[0] if nombre_legible else "la persona"
    if not pruebas_con_alerta:
        lineas.append(
            f"Por el momento, los indicadores de salud de {nombre_corto} "
            "son favorables. El equipo médico continuará monitoreando su evolución."
        )
    else:
        lineas.append(
            f"El equipo médico está atento a estos parámetros y proporcionará seguimiento "
            f"para que {nombre_corto} mejore. Es normal que durante el tratamiento algunos valores se alteren; "
            "lo importante es el monitoreo permanente."
        )
    
    return "\n".join(lineas)


# ═══════════════════════════════════════════════════════════════════════
# 7. FUNCIÓN PRINCIPAL — llamada desde el endpoint POST /chat en main.py
# ═══════════════════════════════════════════════════════════════════════
 
def procesar_mensaje(mensaje: str, ciu: Optional[str] = None) -> Dict[str, Any]:
    """
    Punto de entrada único del NLP.
 
    Parámetros:
        mensaje: texto tal cual lo escribió el usuario.
        ciu:     CIU asociado a la conversación, si el frontend ya lo tiene
                 (por ejemplo, en el flujo de "ver expediente").
 
    Retorna:
        {"respuesta": str, "accion": Optional[str]}
 
    Los valores de "accion" se mantienen compatibles con el frontend
    existente (js/chatbot.js): "pedir_ciu_registro" y "pedir_ciu_expediente"
    siguen significando exactamente lo mismo que antes.
    """
    texto_norm = normalizar_texto(mensaje)
    ctx = _obtener_contexto(ciu)
    esperando = ctx.get("esperando")

    # ── 0a) Emergencia física — prioridad máxima (sangrado, fiebre alta, dolor fuerte)
    if es_emergencia_fisica(texto_norm):
        registrar_alerta_fisica(ciu, mensaje)
        _limpiar_espera(ciu)
        return {
            "respuesta": (
                "⚠️ ATENCIÓN: Se ha detectado una posible emergencia médica. "
                "Por favor, avisa de inmediato al personal de guardia del albergue o llama al número de emergencias. "
                "He registrado una alerta para el equipo de turno."
            ),
            "accion": None,
        }

    # ── 0b) Riesgo emocional — SIEMPRE tiene prioridad sobre lo demás ──
    if es_riesgo_emocional(texto_norm):
        registrar_alerta_riesgo(ciu, mensaje)
        _limpiar_espera(ciu)
        return {"respuesta": RESPUESTA_ALERTA_RIESGO, "accion": None}
 
    # ── 1) Si el bot había hecho una pregunta de seguimiento, interpretar
    #        la respuesta corta del usuario en ese contexto ──
    if esperando == "confirmar_contacto_equipo":
        # Pregunta previa: "¿Quieres que avise al equipo médico/psicología?"
        if es_afirmacion(texto_norm):
            # Registrar simple solicitud de contacto — la integración real
            # debe notificar al equipo por el canal operativo del albergue.
            print(f"[CHATBOT] Solicitud de contacto equipo para CIU={ciu or 'sin_ciu'} mensaje={mensaje}")
            _limpiar_espera(ciu)
            return {
                "respuesta": (
                    "Entiendo. Avisaré al equipo de ALDIMI para que se pongan en contacto. "
                    "El personal evaluará la situación y te responderá a la brevedad."
                ),
                "accion": None,
            }
        if es_negacion(texto_norm):
            _limpiar_espera(ciu)
            return {
                "respuesta": "De acuerdo, no avisaré al equipo por ahora. Si cambias de opinión, dímelo.",
                "accion": None,
            }
        # Si no fue ni sí/no, permitir continuar al flujo normal
        _limpiar_espera(ciu)

    if esperando == "confirmacion_otro_servicio":
        if es_agradecimiento(texto_norm):
            _limpiar_espera(ciu)
            return {"respuesta": "¡De nada! Fue un gusto ayudarte. 😊", "accion": None}
        if es_negacion(texto_norm):
            _limpiar_espera(ciu)
            return {
                "respuesta": "Entendido, quedo por aquí si necesitas algo más. ¡Que tengas un buen día!",
                "accion": None,
            }
        if es_afirmacion(texto_norm):
            _limpiar_espera(ciu)
            return {
                "respuesta": "Claro, cuéntame qué necesitas (horarios, donaciones, expedientes, "
                             "alertas clínicas, reglamento, servicios, requisitos de admisión o visitas).",
                "accion": None,
            }
        # Si no fue ni sí/no/gracias, se limpia el contexto y seguimos
        # abajo tratándolo como un mensaje nuevo (no forzamos al usuario
        # a repetir nada).
        _limpiar_espera(ciu)
 
    # ── 2) Saludo / despedida (no dependen de contexto previo) ──
    if es_saludo(texto_norm) and len(texto_norm.split()) <= 4:
        return {
            "respuesta": "¡Hola! Soy el asistente de ALDIMI. ¿En qué puedo ayudarte hoy?",
            "accion": None,
        }
    if es_despedida(texto_norm):
        return {"respuesta": "¡Hasta luego! Aquí estaré si necesitas algo más.", "accion": None}
    if es_agradecimiento(texto_norm):
        return {"respuesta": "¡De nada! Fue un gusto ayudarte. 😊", "accion": None}
 
    if esperando in ("pedir_ciu_expediente", "pedir_ciu_alertas") and es_ciu_valido(mensaje):
        prev_esperando = esperando
        ciu_buscar = mensaje.strip().upper()
        bd = cargar_bd()
        print(f"[CHATBOT] Buscando expediente para CIU {ciu_buscar}. Base de datos tiene {len(bd)} registros.")
        registro = _buscar_registro_por_ciu(bd, ciu_buscar)
        # Normalizar limpieza de estado antes de responder
        _limpiar_espera(None)
        if not registro:
            print(f"[CHATBOT] No encontrado: {ciu_buscar}")
            return {
                "respuesta": f"No encontré un expediente registrado con CIU {ciu_buscar}.",
                "accion": None,
            }

        # Si la espera era para ALERTAS, delegar al módulo `alertas.py`
        if prev_esperando == "pedir_ciu_alertas":
            try:
                respuesta = filtrar_alertas_criticas(registro, ciu_buscar)
            except Exception:
                respuesta = "Ocurrió un error al filtrar las alertas clínicas."
            return {"respuesta": respuesta, "accion": None}

        # Flujo por defecto: expediente completo (comportamiento legacy)
        datos = _extraer_datos_personales_desde_registro(registro, ciu_buscar)

        informes = registro.get("informes_laboratorio", []) or []
        alertas = registro.get("alertas_clinicas", []) or []

        print(f"[CHATBOT] Encontrado: {ciu_buscar} con {len(informes)} informes de lab y {len(alertas)} alertas")

        respuesta_partes = [
            f"✅ Datos extraídos:",
            f"   CIU: {ciu_buscar}",
            f"   Nombre: {datos.get('nombres', 'NO_DETECTADO')} {datos.get('apellidos', 'NO_DETECTADO')}",
            f"   Fecha nac.: {datos.get('fecha_nacimiento', 'NO_DETECTADO')}",
        ]

        if informes:
            respuesta_partes.append(f"\n📋 Informes de laboratorio: {len(informes)}")
        if alertas:
            respuesta_partes.append(f"⚠️  Alertas clínicas: {len(alertas)}")

        respuesta = "\n".join(respuesta_partes)
        return {"respuesta": respuesta, "accion": None}
 
    # ── 3) Caso especial: viene del flujo "pedir_ciu_expediente" ──
    if texto_norm.startswith("ver expediente") or (ciu and "expediente" in texto_norm):
        if not ciu:
            _actualizar_contexto(ciu, esperando="pedir_ciu_expediente")
            return {
                "respuesta": "Claro, indícame el CIU del paciente para mostrarte su expediente.",
                "accion": "pedir_ciu_expediente",
            }
        bd = cargar_bd()
        registro = _buscar_registro_por_ciu(bd, ciu)
        if not registro:
            return {
                "respuesta": f"No encontré un expediente registrado con CIU {ciu}.",
                "accion": None,
            }
        respuesta = construir_respuesta_expediente(registro) + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio")
        return {"respuesta": respuesta, "accion": None}
 
    # ── 4) Comando literal "REGISTRO" — dispara el flujo real de registro
    #        de paciente (el que ya maneja el frontend: pide CIU y luego
    #        el usuario sube el DNI en la sección OCR). ──
    if texto_norm == "registro":
        return {
            "respuesta": "Perfecto, para iniciar el registro indícame el CIU/DNI del paciente.",
            "accion": "pedir_ciu_registro",
        }
 
    intencion = detectar_intencion(texto_norm)
 
    # Si no encontramos una intención clara con el detector actual,
    # delegamos al `PatientNLP` ligero que usa variantes ampliadas y
    # prioriza emergencias/riesgo emocional. Esto mejora respuestas
    # espontáneas durante la conversación del paciente.
    if not intencion:
        try:
            nlp = get_nlp()
            resultado = nlp.classify_and_respond(mensaje, ciu)
        except Exception:
            resultado = None

        if resultado:
            accion_nlp = resultado.get("accion")
            intent_nlp = resultado.get("intent")
            respuesta_nlp = resultado.get("respuesta")

            if accion_nlp == "alerta_fisica":
                # Registrar y responder con instrucción de urgencia
                registrar_alerta_fisica(ciu, mensaje)
                _limpiar_espera(ciu)
                return {"respuesta": respuesta_nlp, "accion": None}

            if accion_nlp == "confirmar_contacto":
                # Guardar estado para la siguiente respuesta corta (sí/no)
                _actualizar_contexto(ciu, esperando="confirmar_contacto_equipo")
                return {"respuesta": respuesta_nlp, "accion": None}

            if intent_nlp in RESPUESTAS_INFORMATIVAS:
                _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio", ultima_intencion=intent_nlp)
                return {"respuesta": respuesta_nlp + f"\n\n{PREGUNTA_OTRO_SERVICIO}", "accion": None}

            if respuesta_nlp:
                # Respuesta general retornada por PatientNLP
                return {"respuesta": respuesta_nlp, "accion": None}
    if intencion == "admision":
        respuesta = RESPUESTAS_INFORMATIVAS["admision"] + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio", ultima_intencion=intencion)
        return {"respuesta": respuesta, "accion": None}
 
    if intencion == "evolucion":
        if ciu:
            bd = cargar_bd()
            registro = _buscar_registro_por_ciu(bd, ciu)
            if not registro:
                return {"respuesta": f"No encontré un expediente registrado con CIU {ciu}.", "accion": None}
            respuesta = (
                "Aquí tienes un resumen de la evolución clínica del paciente:\n"
                + construir_respuesta_expediente(registro)
                + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
            )
            _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio")
            return {"respuesta": respuesta, "accion": None}
        _actualizar_contexto(ciu, esperando="pedir_ciu_expediente")
        return {
            "respuesta": "Para revisar la evolución necesito el CIU del paciente.",
            "accion": "pedir_ciu_expediente",
        }
 
    if intencion == "expediente":
        if ciu:
            bd = cargar_bd()
            registro = _buscar_registro_por_ciu(bd, ciu)
            if not registro:
                return {"respuesta": f"No encontré un expediente registrado con CIU {ciu}.", "accion": None}
            respuesta = construir_respuesta_expediente(registro) + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
            _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio")
            return {"respuesta": respuesta, "accion": None}
        _actualizar_contexto(ciu, esperando="pedir_ciu_expediente")
        return {
            "respuesta": "Claro, indícame el CIU del paciente para mostrarte su expediente.",
            "accion": "pedir_ciu_expediente",
        }
 
    if intencion == "pregunta_otro_usuario":
        # Usuario pregunta por salud de OTRO paciente (no es su CIU actual)
        # Buscar el CIU en el contexto o solicitar que lo proporcione
        if not ciu:
            _actualizar_contexto(ciu, esperando="pedir_ciu_pregunta_otro")
            return {
                "respuesta": "Claro, por favor indícame el CIU del paciente cuya salud te interesa conocer.",
                "accion": "pedir_ciu_expediente",
            }
        
        # Buscar el registro del otro usuario
        bd = cargar_bd()
        registro = _buscar_registro_por_ciu(bd, ciu)
        if not registro:
            return {
                "respuesta": f"No encontré un expediente registrado con CIU {ciu}. Verifica que el CIU sea correcto.",
                "accion": None,
            }
        
        # Construir respuesta tranquilizadora con análisis de alertas
        respuesta = construir_respuesta_salud_otro_usuario(registro, ciu) + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio")
        return {"respuesta": respuesta, "accion": None}

    if intencion == "alertas_clinicas":
        # Si no tenemos CIU en el contexto, pedimos el CIU pero marcamos
        # el estado interno como `pedir_ciu_alertas` para distinguirlo
        # del flujo de expediente.
        if not ciu:
            _actualizar_contexto(ciu, esperando="pedir_ciu_alertas")
            return {
                "respuesta": "Indícame el CIU del paciente para revisar sus alertas clínicas.",
                "accion": "pedir_ciu_alertas",
            }

        bd = cargar_bd()
        registro = _buscar_registro_por_ciu(bd, ciu)
        if not registro:
            return {"respuesta": f"No encontré un expediente registrado con CIU {ciu}.", "accion": None}

        try:
            respuesta = filtrar_alertas_criticas(registro, ciu)
        except Exception:
            respuesta = "Ocurrió un error al filtrar las alertas clínicas."

        respuesta += f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio")
        return {"respuesta": respuesta, "accion": None}

    # ===== Manejo de nuevas intenciones de soporte al paciente =====
    if intencion == "pronostico_salud":
        # No dar pronósticos médicos; ofrecer contención y conectar con equipo.
        if ciu:
            _actualizar_contexto(ciu, esperando="confirmar_contacto_equipo")
            return {
                "respuesta": (
                    "Entiendo que tiene muchas dudas sobre el futuro y es normal sentirse así. "
                    "No puedo ofrecer un pronóstico médico aquí. Si desea, puedo avisar al equipo médico/psicología para que lo contacten y revisen el expediente del paciente. ¿Desea que lo haga?"
                ),
                "accion": None,
            }
        else:
            _actualizar_contexto(ciu, esperando="confirmar_contacto_equipo")
            return {
                "respuesta": (
                    "Sé que es difícil no saber qué sucederá. No puedo dar pronósticos médicos por texto, pero puedo contactar al equipo médico o de psicología para que le brinden información y apoyo. ¿Desea que lo notifique?"
                ),
                "accion": None,
            }

    if intencion == "contexto_historial":
        respuesta = (
            "ALDIMI accede a la información asociada al CIU del paciente: registros de referencia médica, datos extraídos del DNI con OCR, y los informes de laboratorio que fueron cargados al expediente. "
            "La información se usa para brindar continuidad de atención y se protege según las políticas de privacidad del albergue. Si desea, puedo mostrar el expediente si me indica el CIU.")
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio")
        return {"respuesta": respuesta, "accion": None}

    if intencion == "cuidados_recomendaciones":
        if ciu:
            bd = cargar_bd()
            registro = _buscar_registro_por_ciu(bd, ciu)
            if registro:
                recomendaciones = generar_recomendaciones(registro)
                if recomendaciones:
                    texto = "Recomendaciones orientativas según las alertas actuales:\n" + "\n".join(recomendaciones)
                    texto += "\n\nEstas recomendaciones son informativas y no sustituyen la evaluación médica. ¿Desea que avise al equipo para una consulta?"
                    _actualizar_contexto(ciu, esperando="confirmar_contacto_equipo")
                    return {"respuesta": texto, "accion": None}
                else:
                    return {"respuesta": "No hay recomendaciones específicas registradas en el expediente. Si lo desea, puedo pedir al equipo médico que revise el caso.", "accion": None}
            else:
                return {"respuesta": f"No encontré un expediente con CIU {ciu}. Si me indica el CIU puedo revisar y brindarle recomendaciones.", "accion": "pedir_ciu_expediente"}
        else:
            return {"respuesta": "Puedo dar recomendaciones generales, pero para recomendaciones personalizadas necesito el CIU del paciente. ¿Desea indicarlo?", "accion": "pedir_ciu_expediente"}

    if intencion == "contencion_emocional":
        # Contención empática no clínica: validar emoción y ofrecer contacto humano.
        _actualizar_contexto(ciu, esperando="confirmar_contacto_equipo")
        return {
            "respuesta": (
                "Siento que esté pasando por un momento difícil. Es normal sentir miedo o tristeza. "
                "Si quiere, puedo avisar al equipo de apoyo psicosocial para que lo acompañen. ¿Desea que lo haga?"
            ),
            "accion": None,
        }
 
    if intencion in RESPUESTAS_INFORMATIVAS:
        respuesta = RESPUESTAS_INFORMATIVAS[intencion] + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio", ultima_intencion=intencion)
        return {"respuesta": respuesta, "accion": None}
    
    return {"respuesta": RESPUESTA_FALLBACK, "accion": None}
 