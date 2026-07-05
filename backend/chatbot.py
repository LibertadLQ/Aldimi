from __future__ import annotations
 
import difflib
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
 
from db import cargar_bd
 
 
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
    "quiero mas informacion", "cuentame mas", "sigue",
]
 
_VARIANTES_NEGACION = [
    "no", "no gracias", "nada mas", "eso es todo", "asi esta bien",
    "no por ahora", "negativo", "esta bien asi", "ninguna", "no necesito nada mas",
]
 
_VARIANTES_AGRADECIMIENTO = [
    "gracias", "muchas gracias", "muy amable", "te agradezco", "mil gracias",
    "gracias por la ayuda", "genial gracias",
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
    return coincide_variante(texto_norm, _VARIANTES_AGRADECIMIENTO, umbral=0.75)
 
 
def es_saludo(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_SALUDO, umbral=0.85)
 
 
def es_despedida(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_DESPEDIDA, umbral=0.85)
 
 
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
        "expediente", "ver expediente", "consultar expediente",
        "historial clinico", "historia clinica", "ficha del paciente",
        "informacion del paciente", "datos del paciente",
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
    "   horario | registro | donaciones | expedientes\n"
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
 
 
def construir_respuesta_expediente(registro: Dict[str, Any]) -> str:
    """Arma el mensaje completo: datos básicos + evolución + recomendaciones."""
    datos = registro.get("datos_personales", {}) or {}
    ciu = registro.get("ciu", "")
 
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
 
    # ── 0) Riesgo emocional — SIEMPRE tiene prioridad sobre todo lo demás ──
    if es_riesgo_emocional(texto_norm):
        registrar_alerta_riesgo(ciu, mensaje)
        _limpiar_espera(ciu)
        return {"respuesta": RESPUESTA_ALERTA_RIESGO, "accion": None}
 
    # ── 1) Si el bot había hecho una pregunta de seguimiento, interpretar
    #        la respuesta corta del usuario en ese contexto ──
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
 
    # ── 3) Caso especial: viene del flujo "pedir_ciu_expediente" ──
    if texto_norm.startswith("ver expediente") or (ciu and "expediente" in texto_norm):
        if not ciu:
            _actualizar_contexto(ciu, esperando="pedir_ciu_expediente")
            return {
                "respuesta": "Claro, indícame el CIU del paciente para mostrarte su expediente.",
                "accion": "pedir_ciu_expediente",
            }
        bd = cargar_bd()
        registro = bd.get(ciu.strip().upper())
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
 
    if intencion == "admision":
        respuesta = RESPUESTAS_INFORMATIVAS["admision"] + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio", ultima_intencion=intencion)
        return {"respuesta": respuesta, "accion": None}
 
    if intencion == "expediente":
        if ciu:
            bd = cargar_bd()
            registro = bd.get(ciu.strip().upper())
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
 
    if intencion == "alertas_clinicas":
        if not ciu:
            _actualizar_contexto(ciu, esperando="pedir_ciu_expediente")
            return {
                "respuesta": "Indícame el CIU del paciente para revisar sus alertas clínicas.",
                "accion": "pedir_ciu_expediente",
            }
        bd = cargar_bd()
        registro = bd.get(ciu.strip().upper())
        alertas = (registro or {}).get("alertas_clinicas", []) or []
        if not alertas:
            respuesta = f"El paciente {ciu} no presenta alertas clínicas activas."
        else:
            detalle = "\n".join(
                f"• {a.get('prueba', 'Prueba')}: {a.get('tipo', '')} ({a.get('valor', '')} {a.get('unidad', '')})"
                for a in alertas if isinstance(a, dict)
            )
            respuesta = f"Alertas clínicas activas para {ciu}:\n{detalle}"
        respuesta += f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio")
        return {"respuesta": respuesta, "accion": None}
 
    if intencion in RESPUESTAS_INFORMATIVAS:
        respuesta = RESPUESTAS_INFORMATIVAS[intencion] + f"\n\n{PREGUNTA_OTRO_SERVICIO}"
        _actualizar_contexto(ciu, esperando="confirmacion_otro_servicio", ultima_intencion=intencion)
        return {"respuesta": respuesta, "accion": None}
    
    return {"respuesta": RESPUESTA_FALLBACK, "accion": None}
 