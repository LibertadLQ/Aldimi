# -*- coding: utf-8 -*-
"""
db.py — Persistencia local de ALDIMI

Lee y escribe `ALDIMI_DB/aldimi_pacientes.json` y `ALDIMI_DB/aldimi_sesiones.json`.
"""

import json
from datetime import datetime

from .storage import DB_PATH, SESSION_PATH


def cargar_bd() -> dict:
    if not DB_PATH.exists():
        return {}

    with open(DB_PATH, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
        data = json.loads(contenido) if contenido else {}
        if isinstance(data, dict) and "pacientes" in data and isinstance(data["pacientes"], dict):
            return data["pacientes"]
        return data if isinstance(data, dict) else {}


def guardar_bd(bd: dict) -> None:
    payload = {
        "sesion": {
            "ultima_actualizacion": datetime.now().isoformat(),
            "archivo": DB_PATH.name,
        },
        "pacientes": bd,
    }

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def cargar_sesiones() -> list:
    if not SESSION_PATH.exists():
        return []
    with open(SESSION_PATH, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
        return json.loads(contenido) if contenido else []


def guardar_sesiones(sesiones: list) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(sesiones, f, indent=2, ensure_ascii=False)
