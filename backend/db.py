# -*- coding: utf-8 -*-
"""
db.py — Persistencia local de ALDIMI

Lee y escribe `ALDIMI_DB/aldimi_pacientes.json` y `ALDIMI_DB/aldimi_sesiones.json`.
"""

import json
import os
from datetime import datetime

from .storage import DB_PATH, SESSION_PATH


def _backup_db_file() -> None:
    backup_path = DB_PATH.with_suffix(DB_PATH.suffix + ".bak")
    if not backup_path.exists():
        DB_PATH.replace(backup_path)
        DB_PATH.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")


def cargar_bd() -> dict:
    if not DB_PATH.exists():
        return {}

    with open(DB_PATH, "r", encoding="utf-8") as f:
        contenido = f.read()

    if not contenido.strip():
        return {}

    try:
        data = json.loads(contenido)
    except json.JSONDecodeError as exc:
        backup_path = DB_PATH.with_suffix(DB_PATH.suffix + ".bak")
        if not backup_path.exists():
            backup_path.write_text(contenido, encoding="utf-8")
            print(f"[DB] Backup creado en {backup_path}")

        decoder = json.JSONDecoder()
        try:
            obj, idx = decoder.raw_decode(contenido)
            resto = contenido[idx:]
            if resto.strip().strip("\x00") != "":
                print("[DB] Aviso: se detectó contenido extra no JSON al final de aldimi_pacientes.json; se recuperará el prefijo JSON válido.")

            contenido_limpio = contenido[:idx].rstrip()
            data = json.loads(contenido_limpio)
            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            print(f"[DB] Error irreparable al decodificar aldimi_pacientes.json: {exc}")
            return {}

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
    tmp_path = DB_PATH.with_suffix(DB_PATH.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, DB_PATH)


def cargar_sesiones() -> list:
    if not SESSION_PATH.exists():
        return []
    with open(SESSION_PATH, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
        return json.loads(contenido) if contenido else []


def guardar_sesiones(sesiones: list) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SESSION_PATH.with_suffix(SESSION_PATH.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(sesiones, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, SESSION_PATH)
