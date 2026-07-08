# -*- coding: utf-8 -*-
"""
backend/alertas.py

Lógica de evaluación de pruebas para generar alertas con severidad y sugerencias.
"""
from typing import List, Dict, Any, Optional
import datetime
import re


_DEFAULT_REFERENCIAS = {
    # Hematología
    "hemoglobina": (12.0, 17.5),      # g/dL
    "hematocrito": (36.0, 50.0),      # %
    "leucocitos": (4.0, 11.0),        # x10³/µL
    "plaquetas": (150.0, 450.0),      # x10³/µL
    "neutrófilos": (1500.0, 8000.0),  # absolutos
    
    # Glucosa y metabolismo
    "glucosa": (70.0, 100.0),         # mg/dL (fasting)
    
    # Función renal
    "creatinina": (0.6, 1.3),         # mg/dL
    "urea": (10.0, 50.0),             # mg/dL
    "bun": (10.0, 50.0),              # mg/dL (same as urea)
    
    # Electrolitos
    "sodio": (135.0, 145.0),          # mEq/L
    "potasio": (3.5, 5.2),            # mEq/L
    "calcio": (8.5, 10.5),            # mg/dL
    
    # Hígado
    "ast": (0.0, 40.0),               # U/L
    "alt": (0.0, 40.0),               # U/L
    "bilirrubina": (0.3, 1.2),        # mg/dL total
    
    # Coagulación
    "inr": (0.8, 1.2),                # ratio
    
    # Inflamación
    "proteína c reactiva": (0.0, 5.0),  # mg/L
    "crp": (0.0, 5.0),                # mg/L (same as PCR)
    "pcr": (0.0, 5.0),                # mg/L
    
    # Lípidos
    "colesterol": (0.0, 200.0),       # mg/dL total
    "triglicéridos": (0.0, 150.0),    # mg/dL
}


def _parse_float_valor(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    texto = str(valor).strip().replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", texto)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _infer_from_referencia_default(nombre: str, valor: float) -> Optional[str]:
    low_high = None
    if not nombre or valor is None:
        return None
    nlow = nombre.lower()
    for clave, (low, high) in _DEFAULT_REFERENCIAS.items():
        if clave in nlow:
            if low is not None and valor < low:
                return "BAJO"
            if high is not None and valor > high:
                return "ALTO"
            return None
    return None


_SUGGESTIONS = {
    "Anemia Crítica": "Reposo absoluto, control de signos vitales y posible transfusión. Contactar equipo médico.",
    "Anemia Moderada": "Dieta rica en hierro, evitar esfuerzos; evaluar según síntomas.",
    "Trombocitopenia Grave": "Evitar procedimientos invasivos; riesgo de sangrado. Consultar hematología.",
    "Neutropenia Severa": "Aislamiento si fiebre, control de temperatura, considerar profilaxis/investigación infecciosa.",
    "Desequilibrio Electrolítico": "Monitoreo cardíaco y corrección según protocolo; derivar al médico.",
    "Insuficiencia Renal": "Ajustar hidratación y revisar medicamentos nefrotóxicos; valoración médica urgente.",
    "Inflamación/Posible infección": "Vigilar fiebre y signos de infección; derivar si febril o con compromiso clínico.",
}


def evaluar_prueba(prueba: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evalúa una `prueba` (diccionario con keys como nombre, valor, flag, referencia)
    y retorna una alerta enriquecida o None.
    """
    nombre = str(prueba.get("nombre", "") or "").strip()
    valor_raw = prueba.get("valor")
    flag = str(prueba.get("flag", "") or "").upper()
    referencia = str(prueba.get("referencia", "") or "").strip()

    valor = _parse_float_valor(valor_raw)

    # Priorizar flag explícito
    tipo = None
    if flag:
        if "H" in flag or any(k in flag for k in ["POSITIVO", "REACTIVO", "DETECTADO", "RESISTENTE"]):
            tipo = "ALTO"
        elif "L" in flag or any(k in flag for k in ["NEGATIVO", "NO DETECTADO", "ABSENT"]):
            tipo = "BAJO"

    # Si no hay flag, intentar referencia explícita (formato min-max)
    if tipo is None and referencia:
        m = re.search(r"([\d.,]+)\s*[-–]\s*([\d.,]+)", referencia)
        if m and valor is not None:
            low = float(m.group(1).replace(",", "."))
            high = float(m.group(2).replace(",", "."))
            if valor < low:
                tipo = "BAJO"
            elif valor > high:
                tipo = "ALTO"

    # Fallback por referencias por defecto
    if tipo is None and valor is not None:
        tipo = _infer_from_referencia_default(nombre, valor)

    if not tipo:
        return None

    # Severidad heurística
    severity = "medium"
    reason = "flag" if flag else ("referencia" if referencia else "default_ref")

    # reglas específicas por tipo de prueba
    nl = nombre.lower()
    
    if "hemoglob" in nl:
        # Hemoglobina: crítica <7, high <10, alerta si fuera de rango
        if valor is not None and valor < 7.0:
            severity = "critical"
            title = "Anemia Crítica"
            suggestion = "Reposo absoluto, control de signos vitales y posible transfusión. Contactar equipo médico."
        elif valor is not None and valor < 10.0:
            severity = "high"
            title = "Anemia Moderada"
            suggestion = "Dieta rica en hierro, evitar esfuerzos; evaluar según síntomas."
        elif valor is not None and valor > 20.0:
            severity = "high"
            title = "Policitemia"
            suggestion = "Hidratación y monitoreo; valoración médica para descartar poliglobulia vera."
        else:
            title = "Hemoglobina fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "hematocrito" in nl:
        # Hematocrito: crítica <15 o >70, high si fuera de rango
        if valor is not None and (valor < 15.0 or valor > 70.0):
            severity = "critical" if valor < 15.0 else "high"
            title = "Hematocrito Crítico"
            suggestion = "Evaluación médica urgente. Posible transfusión si <15%."
        else:
            title = "Hematocrito fuera de rango"
            suggestion = "Revisar con personal médico."
    
    elif "plaquet" in nl or "plaquetas" in nl:
        # Plaquetas: crítica <20k, high <50k
        if valor is not None and valor < 20000:
            severity = "critical"
            title = "Trombocitopenia Grave"
            suggestion = "Evitar procedimientos invasivos; riesgo de sangrado. Consultar hematología."
        elif valor is not None and valor < 50000:
            severity = "high"
            title = "Trombocitopenia"
            suggestion = "Evitar procedimientos invasivos; seguimiento hematológico."
        elif valor is not None and valor > 1000000:
            severity = "high"
            title = "Trombocitosis"
            suggestion = "Investigar causa; posible síndrome mieloproliferativo."
        else:
            title = "Plaquetas fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "leucocito" in nl:
        # Leucocitos: crítica <1 o >50
        if valor is not None and (valor < 1.0 or valor > 50.0):
            severity = "critical"
            title = "Recuento de Leucocitos Crítico"
            suggestion = "Evaluación médica urgente; posible infección severa o leucemia."
        elif valor is not None and valor < 4.0:
            severity = "high"
            title = "Leucopenia"
            suggestion = "Monitoreo de infecciones; considerar aislamiento si <1000."
        elif valor is not None and valor > 11.0:
            severity = "medium"
            title = "Leucocitosis"
            suggestion = "Investigar infección, inflamación o hematológica."
        else:
            title = "Leucocitos fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "neutro" in nl or "neutróf" in nl or "neutrofil" in nl:
        # Neutrófilos: crítica <500, high <1500
        if valor is not None and valor < 500:
            severity = "critical"
            title = "Neutropenia Severa"
            suggestion = "Aislamiento si fiebre, control de temperatura, considerar profilaxis/investigación infecciosa."
        elif valor is not None and valor < 1500:
            severity = "high"
            title = "Neutropenia"
            suggestion = "Monitoreo de infecciones; evaluar causa (fármacos, enfermedad)."
        else:
            title = "Neutrófilos fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "glucosa" in nl:
        # Glucosa: crítica <40 o >400, high si <70 o >126 (fasting)
        if valor is not None and (valor < 40.0 or valor > 400.0):
            severity = "critical"
            title = "Glucosa Crítica"
            suggestion = "Emergencia endocrinológica; contactar médico inmediatamente."
        elif valor is not None and (valor < 70.0 or valor > 126.0):
            severity = "high"
            title = "Glucosa Elevada/Baja"
            suggestion = "Ajuste de insulina/hipoglucemiantes; monitoreo frecuente de glucosa."
        else:
            title = "Glucosa fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "creatinina" in nl:
        # Creatinina: crítica >10, high si >1.3
        if valor is not None and valor > 10.0:
            severity = "critical"
            title = "Insuficiencia Renal Crítica"
            suggestion = "Evaluación urgente de función renal; posible necesidad de diálisis."
        elif valor is not None and valor > 1.3:
            severity = "high"
            title = "Creatinina Elevada"
            suggestion = "Ajustar hidratación y revisar medicamentos nefrotóxicos; valoración médica."
        else:
            title = "Creatinina fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif any(x in nl for x in ("urea", "bun")):
        # Urea/BUN: high si >50
        if valor is not None and valor > 50.0:
            severity = "high"
            title = "Urea Elevada"
            suggestion = "Investigar función renal y deshidratación; monitoreo."
        else:
            title = "Urea fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "sodio" in nl:
        # Sodio: crítica <120 o >160, high si <135 o >145
        if valor is not None and (valor < 120.0 or valor > 160.0):
            severity = "critical"
            title = "Sodio Crítico"
            suggestion = "Emergencia; posible convulsiones o edema cerebral. Contactar médico."
        elif valor is not None and (valor < 135.0 or valor > 145.0):
            severity = "high"
            title = "Desequilibrio de Sodio"
            suggestion = "Ajuste de hidratación y electrolitos; monitoreo cardíaco."
        else:
            title = "Sodio fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "potasio" in nl or re.search(r"\bk\b|\bk\)", nl):
        # Potasio: crítica <2.5 o >6.5, high si <3.5 o >5.2
        if valor is not None and (valor < 2.5 or valor > 6.5):
            severity = "critical"
            title = "Potasio Crítico"
            suggestion = "Emergencia cardiológica (arritmia); monitoreo ECG, contactar médico."
        elif valor is not None and (valor < 3.5 or valor > 5.2):
            severity = "high"
            title = "Desequilibrio Electrolítico (Potasio)"
            suggestion = "Monitoreo cardíaco y corrección según protocolo; derivar al médico."
        else:
            title = "Potasio fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "calcio" in nl:
        # Calcio: crítica <6 o >13, high si <8.5 o >10.5
        if valor is not None and (valor < 6.0 or valor > 13.0):
            severity = "critical"
            title = "Calcio Crítico"
            suggestion = "Emergencia; riesgo de tetania (hipocalcemia) o arritmias (hipercalcemia)."
        elif valor is not None and (valor < 8.5 or valor > 10.5):
            severity = "high"
            title = "Desequilibrio de Calcio"
            suggestion = "Ajuste de vitamina D y fósforo; monitoreo."
        else:
            title = "Calcio fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif any(x in nl for x in ("ast", "alt", "transaminasa")):
        # AST/ALT: high si >40
        if valor is not None and valor > 40.0:
            severity = "high" if valor < 120.0 else "critical"
            title = "Transaminasas Elevadas"
            suggestion = "Investigar hepatitis, cirrosis, lesión hepática; ultrasound/biopsia si persiste."
        else:
            title = "AST/ALT fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "bilirrubina" in nl:
        # Bilirrubina: high si >1.2, crítica si >10
        if valor is not None and valor > 10.0:
            severity = "critical"
            title = "Bilirrubina Crítica"
            suggestion = "Emergencia hepatológica; riesgo de encefalopatía. Contactar médico."
        elif valor is not None and valor > 1.2:
            severity = "high"
            title = "Bilirrubina Elevada"
            suggestion = "Investigar ictericia; descartar obstrucción biliar o hepatitis."
        else:
            title = "Bilirrubina fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "inr" in nl:
        # INR: high si >1.2 (sin anticoagulante), crítica si >5
        if valor is not None and valor > 5.0:
            severity = "critical"
            title = "INR Crítico"
            suggestion = "Riesgo de sangrado severo; contactar hematología/medicina urgentemente."
        elif valor is not None and valor > 1.2:
            severity = "high"
            title = "INR Elevado"
            suggestion = "Evaluación de sangrado; ajuste de anticoagulación si es necesario."
        else:
            title = "INR fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif any(x in nl for x in ("crp", "proteína c reactiva", "pcr")):
        # CRP: high si >5, crítica si >100
        if valor is not None and valor > 100.0:
            severity = "critical"
            title = "CRP Crítica"
            suggestion = "Inflamación/infección severa; investigar urgentemente."
        elif valor is not None and valor > 5.0:
            severity = "high"
            title = "Inflamación/Posible infección"
            suggestion = "Vigilar fiebre y signos de infección; derivar si febril o con compromiso clínico."
        else:
            title = "CRP fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "colesterol" in nl:
        # Colesterol: high si >240
        if valor is not None and valor > 240.0:
            severity = "medium"
            title = "Colesterol Elevado"
            suggestion = "Dieta baja en grasas; evaluar para medicación estatinas."
        else:
            title = "Colesterol fuera de rango"
            suggestion = "Revisar laboratorio."
    
    elif "triglicérido" in nl or "trigicerido" in nl:
        # Triglicéridos: high si >200, crítica si >500 (riesgo pancreatitis)
        if valor is not None and valor > 500.0:
            severity = "critical"
            title = "Triglicéridos Críticos"
            suggestion = "Riesgo de pancreatitis; restricción severa de grasas, considerar fibrato."
        elif valor is not None and valor > 200.0:
            severity = "high"
            title = "Triglicéridos Elevados"
            suggestion = "Dieta baja en grasas y azúcares; ejercicio; posible medicación."
        else:
            title = "Triglicéridos fuera de rango"
            suggestion = "Revisar laboratorio."
    
    else:
        # Fallback para tests desconocidos
        title = f"{nombre} fuera de referencia"
        suggestion = "Revisar resultado con personal médico."

    alerta = {
        "timestamp": datetime.datetime.now().isoformat(),
        "prueba": nombre,
        "valor": valor,
        "unidad": prueba.get("unidad"),
        "tipo": tipo,
        "severity": severity,
        "reason": reason,
        "title": title,
        "suggestion": suggestion,
        "source": prueba.get("source", "ocr"),
    }
    return alerta


def evaluar_pruebas(pruebas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for p in pruebas:
        try:
            a = evaluar_prueba(p)
            if a:
                out.append(a)
        except Exception:
            continue
    return out
# -*- coding: utf-8 -*-
"""Módulo de alertas clínicas: lógica para extraer y formatear solo hallazgos críticos.

Funciones principales:
- filtrar_alertas_criticas(registro, ciu=None) -> str

Este módulo se usa desde `backend/chatbot.py` para mantener la vista de Alertas
separada de la vista de Expediente.
"""

import re
from typing import Any, Dict, List

_FLAGS_ALTO = {"H", "HH", "HIGH", "ALTO"}
_FLAGS_BAJO = {"L", "LL", "LOW", "BAJO"}
_FLAGS_ALERTA = _FLAGS_ALTO | _FLAGS_BAJO


def _tokens(flag: Any) -> set:
    """Separa un valor de flag/tipo en tokens alfabéticos en mayúsculas.

    Se usa coincidencia por token en vez de igualdad exacta para tolerar
    formatos como "ALTO [H]", "High (H)", etc.
    """
    if not flag:
        return set()
    return set(re.findall(r"[A-ZÁÉÍÓÚÑ]+", str(flag).upper()))


def _es_alerta(flag: Any) -> bool:
    if not flag:
        return False
    s = str(flag).upper()
    toks = _tokens(flag)
    # Prefer token-based detection (robust against formatting)
    if toks & _FLAGS_ALERTA:
        return True
    # Fallback: substring-based detection to catch variants like 'ALTO [H]' or 'High (H)'
    for f in _FLAGS_ALERTA:
        if f in s:
            return True
    # Also accept single-letter flags appearing alone or inside brackets
    if re.search(r"\bH\b", s) or re.search(r"\bL\b", s):
        return True
    return False


def _es_alto(flag: Any) -> bool:
    if not flag:
        return False
    s = str(flag).upper()
    toks = _tokens(flag)
    # Token-based detection first
    if toks & _FLAGS_ALTO and not (toks & _FLAGS_BAJO):
        return True
    # Fallback substring detection (ensure no BAJO token present)
    if any(f in s for f in _FLAGS_ALTO) and not any(f in s for f in _FLAGS_BAJO):
        return True
    return False


def filtrar_alertas_criticas(registro: Dict[str, Any], ciu: str = None) -> str:
    """Devuelve texto formateado con SOLO las alertas (H/L) encontradas.

    - Usa `registro['alertas_clinicas']` si está disponible.
    - Si está vacío, recorre `registro['informes_laboratorio']` y filtra
      pruebas cuyo `flag` indique H/L/HH/LL.
    - Formato de salida:
        - Si no hay alertas: mensaje de "no presenta alertas"
        - Si hay alertas: líneas tipo
          "🔺 ALTO: Nombre = valor unidad (Ref: referencia)"
    """
    if registro is None:
        return f"❌ No se encontró información para el CIU {ciu or 'N/D'}."

    ciu_str = str(ciu).strip() if ciu else registro.get("ciu") or "N/D"

    alertas = registro.get("alertas_clinicas") or []
    out_alertas: List[Dict[str, Any]] = []

    # Usar alertas ya calculadas si existen
    if alertas:
        for a in alertas:
            # Normalizar estructura: aceptar items preformateados o dicts con campos
            if isinstance(a, dict):
                flag = a.get("flag") or a.get("tipo") or ""
                if _es_alerta(flag) or a.get("tipo"):
                    out_alertas.append({
                        "nombre": a.get("prueba") or a.get("nombre") or a.get("prueba_nombre") or "Prueba",
                        "valor": a.get("valor", "?"),
                        "unidad": a.get("unidad", ""),
                        "referencia": a.get("referencia", "N/D"),
                        "flag": str(a.get("flag") or a.get("tipo") or "").upper(),
                    })
    # Si no hay alertas precalculadas, buscar en informes
    if not out_alertas:
        informes = registro.get("informes_laboratorio") or []
        for informe in informes:
            pruebas = informe.get("pruebas") or []
            for p in pruebas:
                flag = str(p.get("flag", "")).upper()
                if _es_alerta(flag):
                    out_alertas.append({
                        "nombre": p.get("nombre") or p.get("prueba") or "Prueba",
                        "valor": p.get("valor", "?"),
                        "unidad": p.get("unidad", ""),
                        "referencia": p.get("referencia", "N/D"),
                        "flag": flag,
                    })

    if not out_alertas:
        return (
            f"✅ El paciente {ciu_str} no presenta alertas clínicas "
            f"(todos los valores están en rangos normales o no se detectaron valores fuera de rango)."
        )

    # Construir salida con formato solicitado
    lines: List[str] = [f"🚨 Alertas clínicas — CIU {ciu_str}"]
    lines.append(f"Se detectaron {len(out_alertas)} valores fuera de rango:")

    for a in out_alertas:
        flag = str(a.get("flag", "")).upper()
        icon = "🔺 ALTO" if _es_alto(flag) else "🔻 BAJO"
        nombre = a.get("nombre", "Prueba")
        valor = a.get("valor", "?")
        unidad = a.get("unidad", "")
        ref = a.get("referencia", "N/D")
        lines.append(f"{icon}: {nombre} = {valor} {unidad} (Ref: {ref})")

    return "\n".join(lines)
