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
