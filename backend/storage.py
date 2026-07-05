# -*- coding: utf-8 -*-
"""Rutas compartidas para almacenamiento local de ALDIMI."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _resolve_dir(env_name: str, default_path: Path) -> Path:
    raw = os.environ.get(env_name)
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = (ROOT_DIR / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
    else:
        path = default_path.resolve()
        path.mkdir(parents=True, exist_ok=True)
    return path


DB_DIR = _resolve_dir("ALDIMI_DB_PATH", ROOT_DIR / "ALDIMI_DB")
DNI_DIR = _resolve_dir("DNI_ALDIMI_PATH", ROOT_DIR / "DNI_ALDIMI")
LAB_DIR = _resolve_dir("LAB_ALDIMI_PATH", ROOT_DIR / "LAB_ALDIMI")

DB_PATH = DB_DIR / "aldimi_pacientes.json"
SESSION_PATH = DB_DIR / "aldimi_sesiones.json"
OCR_IMAGES_DIR = DB_DIR / "imagenes_ocr"
