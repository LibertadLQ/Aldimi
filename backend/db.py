# -*- coding: utf-8 -*-
"""
db.py — Persistencia compartida de ALDIMI 2.0

Único punto de lectura/escritura del JSON de pacientes. Tanto main.py
como chatbot.py importan de aquí, así evitamos que cada módulo abra el
archivo por su cuenta (el mismo tipo de duplicación que causaba
problemas en ocr.py con el endpoint repetido).
"""

import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "aldimi_pacientes.json"


def cargar_bd() -> dict:
    if not DB_PATH.exists():
        return {}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
        return json.loads(contenido) if contenido else {}


def guardar_bd(bd: dict) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(bd, f, indent=2, ensure_ascii=False)