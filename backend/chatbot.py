# -*- coding: utf-8 -*-
"""
chatbot.py — Chatbot de texto de ALDIMI 2.0 (FastAPI)

Rescatado y limpiado de la Sección 3 de aldimi.py (notebook de Colab
de tus compañeros). Se descartó por completo el "CNN" que tenían para
clasificar documentos: no era una red entrenada, solo tomaba el
resultado del clasificador por palabras clave y le pegaba encima
probabilidades softmax inventadas con pesos fijos. Ese trabajo real
de clasificación ya lo hace ocr.py con clasificar_documento().

Este módulo SOLO responde texto. No procesa imágenes (eso es ocr.py)
y no reemplaza el guardado de pacientes (eso es /pacientes/guardar
en main.py). Cuando el usuario pide "expediente" o "alertas", este
chatbot LEE el mismo JSON que llena main.py a través de db.py.

Se expone como router de FastAPI para incluirse en main.py:
    from chatbot import router as chatbot_router
    app.include_router(chatbot_router)
"""

import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import cargar_bd

router = APIRouter()

# ─────────────────────────────────────────────────────────────
# Base de conocimiento — respuestas estáticas
# ─────────────────────────────────────────────────────────────

KNOWLEDGE_BASE = {
    "HORARIO": (
        "El horario de atención del Albergue ALDIMI es:\n"
        "   Lunes a Sábado: 9:00 a.m. a 6:00 p.m.\n"
        "   Domingos y feriados: CERRADO.\n"
        "   Urgencias: número de guardia 24/7.\n"
        "¿Desea información sobre algún otro servicio?"
    ),
    "ADMISION": (
        "Para registrar a un paciente:\n"
        "   1. Indíqueme el código CIU o DNI del paciente.\n"
        "   2. Vaya a la sección 'Leer documento' y suba la imagen del DNI.\n"
        "   3. Revise los datos que se extraen automáticamente y corríjalos "
        "si el escaneo salió mal.\n"
        "   4. Confirme para guardar el registro.\n"
        "Repita el mismo proceso con el informe de laboratorio cuando lo tenga."
    ),
    "DONACION": (
        "Canales de donación del Albergue ALDIMI:\n"
        "   • Yape / Plin: 999-888-777\n"
        "   • BCP: Cuenta 123-456789-0-12\n"
        "   • Interbank: 200-3456789-012\n"
        "   • En especie: Ropa, alimentos, medicamentos (lunes a sábado 9am-5pm).\n"
        "   • Voluntariado: coordinacion@aldimi.org"
    ),
    "EXPEDIENTE": (
        "Para consultar el expediente, indique el CIU del paciente.\n"
        "   Formato Perú: 8 dígitos (ej: 42951703)\n"
        "   Formato USA : letra + 6 dígitos (ej: W839927)\n"
        "Podrá ver: datos personales, análisis clínicos y alertas detectadas."
    ),
    "ALERTA": (
        "Se ha detectado una situación de riesgo emocional.\n"
        "Se registrará una alerta para el equipo de soporte psicosocial.\n"
        "El personal evaluará el caso a la brevedad.\n"
        "En emergencias llame al número de guardia 24/7."
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
    "FALLBACK": (
        "No pude entender su consulta. Puede escribir:\n"
        "   horario | registro | donaciones | expedientes\n"
        "   alertas | reglamento | servicios | requisitos | visitas"
    ),
}

FAQ_REGLAMENTO = {
    r"(edad|cuantos.anos|requisito|quien.puede)": (
        "ADMISIÓN: Pacientes oncológicos mayores de 18 años con referencia médica válida. "
        "Se admite un acompañante adulto por paciente."
    ),
    r"(visita|visitar|familiar|quien.viene|cuando.viene)": (
        "VISITAS: Solo familiares directos (padres, hijos, cónyuge). "
        "Deben coordinar previamente con la recepción. "
        "Horario: sábados de 3:00pm a 5:00pm."
    ),
    r"(tiempo|cuanto.tiempo|permanencia|cuanto.puede.quedar|plazo)": (
        "PERMANENCIA: Máxima 30 días prorrogables según evaluación médica. "
        "El equipo evaluará cada caso al vencimiento del plazo."
    ),
    r"(medic|doctor|salud|atencion.medica|cita)": (
        "ATENCIÓN MÉDICA: Evaluación médica semanal para todos los pacientes. "
        "Guardia médica disponible 24 horas ante emergencias. "
        "Se lleva historial clínico completo en el sistema ALDIMI."
    ),
    r"(prohib|no.permit|regla|norma)": (
        "PROHIBICIONES en el albergue:\n"
        "   Sustancias tóxicas o alcohol\n"
        "   Violencia física o verbal\n"
        "   Salidas no autorizadas\n"
        "   Visitas no coordinadas\n"
        "   Ruido después de las 10pm"
    ),
    r"(donar|donacion|ayudar|contribuir|apoyo)": "Ver canales de donación en DONACION.",
    r"(horario|hora|cuando.atiende|abierto)": "Ver horarios en HORARIO.",
}

INTENT_KEYWORDS = {
    "HORARIO": ["horario", "hora", "visita", "apertura", "cierre", "cuando", "abren", "atienden"],
    "ADMISION": ["registrar", "registro", "ingreso", "documentos", "admision", "nuevo", "inscribir", "agregar"],
    "DONACION": ["donar", "donacion", "yape", "cuenta", "ropa", "dinero", "transferencia", "ayuda", "contribuir"],
    "EXPEDIENTE": ["expediente", "historial", "consultar", "buscar", "ver", "datos", "paciente", "ciu"],
    "ALERTA": ["alerta", "alertas", "pendiente", "riesgo", "critico", "notificacion"],
    "EMOCIONAL": ["deprimido", "triste", "llora", "ansiedad", "no quiero", "suicidio", "morir", "sufre", "crisis"],
    "REGLAMENTO": ["reglamento", "normas", "reglas", "politica", "conducta", "prohibido"],
    "SERVICIOS": ["servicios", "ofrecen", "tiene", "alimentacion", "lavanderia", "wifi"],
    "REQUISITOS": ["requisitos", "necesito", "como ingresar", "documentos necesarios"],
    "VISITAS": ["visitas", "familiar", "acompanante", "quien puede visitar"],
}

NEGATIVE_WORDS = {
    "deprimido", "triste", "llora", "ansiedad", "morir", "suicidio", "desesperado",
    "angustia", "dolor", "sufre", "aislado", "decaido", "crisis", "abandono", "vacio", "sin salida",
}

_STOPWORDS_ES = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para",
    "con", "no", "una", "su", "al", "lo", "como", "mas", "pero", "sus", "le", "ya", "o",
    "este", "si", "porque", "esta", "entre", "cuando", "muy", "sin", "sobre", "tambien",
    "me", "hasta", "hay", "donde", "quien", "desde", "nos", "uno", "mi", "que", "ser",
    "es", "si", "te", "tiene",
}

_VOCAL_TRANS = str.maketrans("áéíóúüñ", "aeiooun")


# ─────────────────────────────────────────────────────────────
# NLP — preprocesamiento, intención, FAQ
# ─────────────────────────────────────────────────────────────

def preprocess_text(text: str) -> list:
    t = str(text).lower().translate(_VOCAL_TRANS)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    tokens = re.findall(r"\b[a-z]{2,}\b", t)
    return [tok for tok in tokens if tok not in _STOPWORDS_ES]


def _conf(tokens: list, intent_key: str) -> float:
    kws = INTENT_KEYWORDS.get(intent_key, [])
    if not tokens or not kws:
        return 0.0
    kn = [k.translate(_VOCAL_TRANS) for k in kws]
    hits = sum(1 for t in tokens if any(k in t or t in k for k in kn))
    if hits == 0:
        return 0.0
    base = {1: 0.80, 2: 0.90}.get(hits, 0.95)
    if len(tokens) <= 3:
        base = min(base + 0.05, 1.0)
    return round(base, 3)


def _sentiment_neg_score(tokens: list) -> float:
    if not tokens:
        return 0.0
    neg = {w.translate(_VOCAL_TRANS) for w in NEGATIVE_WORDS}
    hits = sum(1 for t in tokens if t in neg)
    return -(hits / len(tokens))


def buscar_faq_reglamento(msg: str) -> Optional[str]:
    msg_norm = re.sub(r"[aeiouáéíóúüñ]", ".", str(msg).lower())
    for patron, resp in FAQ_REGLAMENTO.items():
        if re.search(patron, msg_norm):
            return resp
    return None


def detect_intent(msg: str):
    tokens = preprocess_text(msg)
    scores = {k: _conf(tokens, k) for k in INTENT_KEYWORDS}
    best = max(scores, key=scores.get)
    conf = scores[best]

    sent = _sentiment_neg_score(tokens)
    if sent < -0.15:
        return "EMOCIONAL", round(abs(sent), 3)

    thresholds = {k: 0.75 for k in INTENT_KEYWORDS}
    thresholds.update({"ADMISION": 0.80, "DONACION": 0.85})
    if best in thresholds and conf >= thresholds[best]:
        return best, conf
    return "FALLBACK", conf


def detect_risk_language(text: str) -> bool:
    """Detecta lenguaje de riesgo psicosocial en el mensaje."""
    risk_kw = [
        "suicidio", "morir", "no quiero vivir", "desesperado", "sin salida",
        "hacerme dano", "lastimarme", "no sirvo", "crisis",
    ]
    t = str(text).lower().translate(_VOCAL_TRANS)
    return any(k.translate(_VOCAL_TRANS) in t for k in risk_kw)


# ─────────────────────────────────────────────────────────────
# Formateo de expediente / alertas a partir de db.cargar_bd()
# ─────────────────────────────────────────────────────────────

def _fmt_expediente(ciu: str, registro: dict) -> str:
    dp = registro.get("datos_personales", {}) or {}
    lineas = [f"📋 EXPEDIENTE {ciu}"]

    if dp:
        lineas.append(f"   👤 Paciente   : {dp.get('nombres', '—')} {dp.get('apellidos', '—')}")
        lineas.append(f"   🎂 Fecha nac. : {dp.get('fecha_nacimiento', '—')}")
    else:
        lineas.append("   (Sin datos personales registrados todavía — falta subir el DNI)")

    informes = registro.get("informes_laboratorio", []) or []
    if informes:
        ultimo = informes[-1]
        lineas.append(f"\n   ─── ÚLTIMO INFORME DE LABORATORIO ({len(informes)} en total) ───")
        pruebas = ultimo.get("pruebas", []) or []
        if pruebas:
            for p in pruebas[:15]:
                flag = f" [{p['flag']}]" if p.get("flag") else ""
                lineas.append(f"   • {p.get('nombre', '?')}: {p.get('valor', '?')} {p.get('unidad', '')}{flag}")
            if len(pruebas) > 15:
                lineas.append(f"   ... y {len(pruebas) - 15} más.")
        else:
            lineas.append("   (informe registrado pero sin pruebas legibles)")
    else:
        lineas.append("\n   (Sin informes de laboratorio registrados)")

    alertas = registro.get("alertas_clinicas", []) or []
    if alertas:
        lineas.append(f"\n   🚨 Alertas clínicas activas: {len(alertas)}")
        for a in alertas[:5]:
            lineas.append(
                f"      ⚠️  {a.get('prueba', '?')} = {a.get('valor', '?')} "
                f"{a.get('unidad', '')} → {a.get('tipo', '')}"
            )
        if len(alertas) > 5:
            lineas.append(f"      ... y {len(alertas) - 5} más.")

    return "\n".join(lineas)


def _fmt_todas_las_alertas(bd: dict) -> str:
    todas = []
    for ciu, registro in bd.items():
        for a in registro.get("alertas_clinicas", []) or []:
            todas.append((ciu, a))

    if not todas:
        return "✅ Sin alertas clínicas pendientes."

    lineas = [f"🔔 ALERTAS CLÍNICAS: {len(todas)} detectadas.\n"]
    for ciu, a in todas[:10]:
        lineas.append(
            f"   [{ciu}] {a.get('prueba', '?')}: {a.get('valor', '?')} "
            f"{a.get('unidad', '')} → {a.get('tipo', '')}"
        )
    if len(todas) > 10:
        lineas.append(f"   ... y {len(todas) - 10} más.")
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────
# Lógica principal del chatbot
# ─────────────────────────────────────────────────────────────

def responder_chat(mensaje: str, ciu: Optional[str] = None) -> dict:
    """
    Resuelve un mensaje de texto y devuelve {intent, confianza, respuesta, accion}.

    'accion' es la señal explícita para el frontend (evita que tenga que
    parsear el texto de la respuesta para saber qué hacer):
      - "pedir_ciu_registro"    -> el siguiente mensaje del usuario debe
                                    tratarse como el CIU/DNI a registrar.
      - "pedir_ciu_expediente"  -> el siguiente mensaje del usuario debe
                                    tratarse como el CIU a consultar.
      - None                     -> respuesta final, no se espera seguimiento.

    Los intents EXPEDIENTE y ALERTA leen el JSON real vía db.cargar_bd();
    el resto son respuestas estáticas de KNOWLEDGE_BASE.
    """
    faq = buscar_faq_reglamento(mensaje)
    if faq:
        return {"intent": "REGLAMENTO", "confianza": 0.95, "respuesta": faq, "accion": None}

    intent, conf = detect_intent(mensaje)

    if intent == "EMOCIONAL":
        # Import perezoso para no crear un ciclo si más adelante quieres
        # registrar la alerta en la BD desde aquí mismo.
        return {"intent": intent, "confianza": conf, "respuesta": KNOWLEDGE_BASE["ALERTA"], "accion": None}

    if intent == "ADMISION":
        return {
            "intent": intent,
            "confianza": conf,
            "respuesta": KNOWLEDGE_BASE["ADMISION"] + "\n\n¿Cuál es el CIU o DNI del paciente?",
            "accion": "pedir_ciu_registro",
        }

    if intent == "EXPEDIENTE":
        ciu_limpio = (ciu or "").strip().upper()
        if not ciu_limpio:
            return {
                "intent": intent,
                "confianza": conf,
                "respuesta": KNOWLEDGE_BASE["EXPEDIENTE"],
                "accion": "pedir_ciu_expediente",
            }
        bd = cargar_bd()
        registro = bd.get(ciu_limpio)
        if not registro:
            return {
                "intent": intent,
                "confianza": conf,
                "respuesta": f"No encontré ningún paciente con CIU {ciu_limpio}.",
                "accion": None,
            }
        return {
            "intent": intent,
            "confianza": conf,
            "respuesta": _fmt_expediente(ciu_limpio, registro),
            "accion": None,
        }

    if intent == "ALERTA":
        bd = cargar_bd()
        return {"intent": intent, "confianza": conf, "respuesta": _fmt_todas_las_alertas(bd), "accion": None}

    respuesta = KNOWLEDGE_BASE.get(intent, KNOWLEDGE_BASE["FALLBACK"])
    return {"intent": intent, "confianza": conf, "respuesta": respuesta, "accion": None}


# ─────────────────────────────────────────────────────────────
# Router FastAPI
# ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    mensaje: str
    ciu: Optional[str] = None  # opcional: solo se usa para intent EXPEDIENTE


@router.post("/chat")
async def chat(req: ChatRequest):
    """
    Punto de entrada único del chatbot para chatbot.html.
    El frontend manda {"mensaje": "...", "ciu": "..."} (ciu es opcional,
    solo hace falta cuando el usuario pide ver un expediente).
    """
    if not req.mensaje or not req.mensaje.strip():
        raise HTTPException(400, "El mensaje no puede estar vacío.")
    return responder_chat(req.mensaje, req.ciu)