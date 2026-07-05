# -*- coding: utf-8 -*-
"""
db.py — Persistencia compartida de ALDIMI 2.0

Único punto de lectura/escritura del JSON de pacientes. Tanto main.py
como chatbot.py importan de aquí, así evitamos que cada módulo abra el
archivo por su cuenta (el mismo tipo de duplicación que causaba
problemas en ocr.py con el endpoint repetido).
"""

import json
from datetime import datetime
import os

from storage import DB_PATH, SESSION_PATH

GDRIVE_ENABLED = os.environ.get("GDRIVE_ENABLED") == "1"
GDRIVE_DB_FOLDER_ID = os.environ.get("GDRIVE_DB_FOLDER_ID")
if GDRIVE_ENABLED and GDRIVE_DB_FOLDER_ID:
    try:
        from drive_sync import get_json_from_drive, upload_json_to_drive
    except Exception:
        get_json_from_drive = None
        upload_json_to_drive = None


def cargar_bd() -> dict:
    # Prefer Drive-backed DB if enabled
    if GDRIVE_ENABLED and GDRIVE_DB_FOLDER_ID and get_json_from_drive:
        try:
            data = get_json_from_drive(GDRIVE_DB_FOLDER_ID, DB_PATH.name)
            if not data:
                return {}
            if isinstance(data, dict) and "pacientes" in data and isinstance(data["pacientes"], dict):
                return data["pacientes"]
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

    if not DB_PATH.exists():
        return {}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
        data = json.loads(contenido) if contenido else {}
        if isinstance(data, dict) and "pacientes" in data and isinstance(data["pacientes"], dict):
            return data["pacientes"]
        return data if isinstance(data, dict) else {}


def guardar_bd(bd: dict) -> None:
    # Prepare payload
    payload = {
        "sesion": {
            "ultima_actualizacion": datetime.now().isoformat(),
            "archivo": DB_PATH.name,
        },
        "pacientes": bd,
    }

    # Try upload to Drive if enabled
    if GDRIVE_ENABLED and GDRIVE_DB_FOLDER_ID and upload_json_to_drive:
        try:
            upload_json_to_drive(GDRIVE_DB_FOLDER_ID, DB_PATH.name, payload)
        except Exception:
            pass

    # Also keep local copy as fallback
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def cargar_sesiones() -> list:
    # Prefer Drive-backed sessions if enabled
    if GDRIVE_ENABLED and GDRIVE_DB_FOLDER_ID and get_json_from_drive:
        try:
            data = get_json_from_drive(GDRIVE_DB_FOLDER_ID, SESSION_PATH.name)
            return data if isinstance(data, list) else []
        except Exception:
            pass

    if not SESSION_PATH.exists():
        return []
    with open(SESSION_PATH, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
        return json.loads(contenido) if contenido else []


def guardar_sesiones(sesiones: list) -> None:
    # Try upload to Drive if enabled
    if GDRIVE_ENABLED and GDRIVE_DB_FOLDER_ID and upload_json_to_drive:
        try:
            upload_json_to_drive(GDRIVE_DB_FOLDER_ID, SESSION_PATH.name, sesiones)
        except Exception:
            pass

    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(sesiones, f, indent=2, ensure_ascii=False)