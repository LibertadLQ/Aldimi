from __future__ import annotations

import json
import random
import difflib
import re
import unicodedata
from typing import Any, Dict, List, Optional

# Para evitar importaciones circulares con `backend.chatbot`, incluimos
# versiones locales de las utilidades de normalización y coincidencia.
def normalizar_texto(texto: str) -> str:
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
    if not texto_norm:
        return False
    for variante in variantes:
        v = normalizar_texto(variante)
        if not v:
            continue
        if re.search(rf"\b{re.escape(v)}\b", texto_norm):
            return True
        if _similitud(texto_norm, v) >= umbral:
            return True
        palabras_msg = texto_norm.split()
        palabras_var = v.split()
        n = len(palabras_var)
        if n <= len(palabras_msg):
            for i in range(len(palabras_msg) - n + 1):
                ventana = " ".join(palabras_msg[i:i + n])
                if _similitud(ventana, v) >= umbral:
                    return True
    return False


_VARIANTES_RIESGO_EMOCIONAL = [
    "quiero morir", "no quiero vivir", "no tengo ganas de vivir",
    "quiero hacerme daño", "me quiero hacer daño", "no aguanto mas",
    "ya no puedo mas", "quiero desaparecer", "no vale la pena seguir",
    "quiero terminar con todo", "me quiero morir",
]

_VARIANTES_EMERGENCIA_SINTOMAS = [
    "sangrando", "estoy sangrando", "sangra", "sangrado",
    "fiebre alta", "tengo fiebre", "fiebre", "dolor insoportable",
    "dolor muy fuerte", "no puedo respirar", "dificultad para respirar",
    "desmaye", "me desmaye", "me desmayé", "vomito sangre", "vomito con sangre",
]


def es_riesgo_emocional(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_RIESGO_EMOCIONAL, umbral=0.82)


def es_emergencia_fisica(texto_norm: str) -> bool:
    return coincide_variante(texto_norm, _VARIANTES_EMERGENCIA_SINTOMAS, umbral=0.78)


_INTENCIONES_DEFAULT: Dict[str, List[str]] = {
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
}

_RESPUESTAS_INFORMATIVAS_DEFAULT: Dict[str, str] = {
    "pronostico_salud": (
        "No puedo decirle exactamente qué pasará, pero estoy aquí para apoyarlo. "
        "Si desea, puedo avisar al equipo de ALDIMI para que le ofrezcan una orientación más personalizada."
    ),
    "contexto_historial": (
        "La información se basa en los datos clínicos y administrativos del expediente. "
        "Si necesita más detalle, puedo solicitar que un miembro del equipo le explique mejor."
    ),
    "cuidados_recomendaciones": (
        "Los cuidados y recomendaciones los define el equipo de salud. "
        "Puedo pedir que un profesional de ALDIMI se comunique con usted para orientarlo."
    ),
    "contencion_emocional": (
        "Lamento que se sienta así. Si quiere, puedo alertar al equipo de soporte emocional para que lo contacten."
    ),
}


class PatientNLP:
    """Clasificador ligero basado en patrones para el chat de ALDIMI.

    - Carga un JSON con intents (ver `nlp/intents_aldimi.json`).
    - Prioriza emergencias físicas y riesgo emocional.
    - Devuelve un dict con 'intent', 'respuesta' y 'accion' sugerida.

    Diseño pensado para integrarse en `backend/chatbot.py`.
    """

    def __init__(self, intents_path: str = "nlp/intents_aldimi.json"):
        self.intents_path = intents_path
        self.intents = self._load_intents(intents_path)
        # Pre-normalizar patrones para búsquedas rápidas
        self._norm_patterns: Dict[str, List[str]] = {}
        for intent in self.intents:
            tag = intent.get("tag")
            patterns = intent.get("patterns", [])
            self._norm_patterns[tag] = [normalizar_texto(p) for p in patterns if p]

    def _load_intents(self, path: str) -> List[Dict[str, Any]]:
        # Intent loading strategy:
        # 1) If a JSON file exists at `path`, load it (backwards-compat).
        # 2) Otherwise, build intents from the in-code `INTENCIONES` map
        #    defined in `backend/chatbot.py` (preferred when no external
        #    JSON is desired).
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("intents", [])
        except FileNotFoundError:
            intents: List[Dict[str, Any]] = []
            for tag, patterns in _INTENCIONES_DEFAULT.items():
                resp = _RESPUESTAS_INFORMATIVAS_DEFAULT.get(tag)
                responses = [resp] if resp else [
                    "Lo siento, puedo ayudar con esa consulta o avisar a un miembro del equipo si lo prefiere."
                ]
                intents.append({"tag": tag, "patterns": patterns, "responses": responses})
            return intents

    def _choose_response(self, intent_obj: Dict[str, Any]) -> str:
        responses = intent_obj.get("responses", [])
        if not responses:
            return "Lo siento, no tengo una respuesta preparada para eso. ¿Desea que le pase a un miembro del equipo?"
        return random.choice(responses)

    def classify_and_respond(self, mensaje: str, ciu: Optional[str] = None) -> Dict[str, Any]:
        texto_norm = normalizar_texto(mensaje)

        # Prioridad 1: emergencias físicas
        if es_emergencia_fisica(texto_norm):
            # No registremos aquí; devolvemos acción para que quien llame haga la notificación
            respuesta = (
                "⚠️ ATENCIÓN: Esto parece una emergencia médica. Por favor, avise de inmediato al personal de guardia o acérquese a enfermería. "
                "Si lo desea, puedo dejar constancia para que el equipo lo atienda.")
            return {"intent": "emergencia_sintomas", "respuesta": respuesta, "accion": "alerta_fisica"}

        # Prioridad 2: riesgo emocional
        if es_riesgo_emocional(texto_norm):
            respuesta = (
                "Se detecta posible riesgo emocional. Puedo avisar al equipo de soporte psicosocial para que lo contacten. "
                "¿Desea que lo haga?")
            return {"intent": "riesgo_emocional", "respuesta": respuesta, "accion": "confirmar_contacto"}

        # Recorremos intents y usamos coincide_variante con las variantes precargadas
        mejor_intent = None
        for intent in self.intents:
            tag = intent.get("tag")
            patrones = self._norm_patterns.get(tag, [])
            if coincide_variante(texto_norm, patrones, umbral=0.78):
                mejor_intent = intent
                break

        if mejor_intent:
            tag = mejor_intent.get("tag")
            respuesta = self._choose_response(mejor_intent)
            accion = None
            # Concentrar acciones para intents sensibles
            if tag == "pronostico_salud":
                accion = "confirmar_contacto"
            if tag == "emergencia_sintomas":
                accion = "alerta_fisica"
            if tag in ("tramites_asistencia_social", "logistica_albergue"):
                accion = "info_operativa"
            return {"intent": tag, "respuesta": respuesta, "accion": accion}

        # Fallback: sugerir opciones y pedir que el usuario elija sí/no
        respuesta = (
            "No entendí exactamente su consulta. Puede preguntarme sobre: horarios, registro, donaciones, expediente, cómo está el paciente, alertas clínicas, reglamento, servicios o visitas. "
            "Si desea, puedo avisar a un miembro del equipo para que le ayude. ¿Desea que lo haga?"
        )
        return {"intent": "fallback", "respuesta": respuesta, "accion": "confirmar_contacto"}


# Pequeña API para uso rápido
_nlp_singleton: Optional[PatientNLP] = None


def get_nlp() -> PatientNLP:
    global _nlp_singleton
    if _nlp_singleton is None:
        _nlp_singleton = PatientNLP()
    return _nlp_singleton


if __name__ == "__main__":
    # Ejemplo rápido
    n = get_nlp()
    ejemplos = [
        "¿Estaré bien después de la operación?",
        "Me siento muy mal, me duele el estómago.",
        "¿A qué hora sirven el almuerzo?",
        "No quiero seguir con esto, ya no puedo."
    ]
    for e in ejemplos:
        r = n.classify_and_respond(e)
        print(e, "->", r)
