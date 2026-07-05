# -*- coding: utf-8 -*-
"""
main.py — Ejecutor local de ALDIMI

Escanea carpetas locales `DNI_ALDIMI` y `LAB_ALDIMI` y persiste resultados
en `ALDIMI_DB/aldimi_pacientes.json` y `ALDIMI_DB/aldimi_sesiones.json`.
"""

import os
from datetime import datetime
from pathlib import Path

from expediente import sincronizar_carpetas


def ejecutar_local(max_images: int = 0) -> dict:
    print("[ALDIMI] Iniciando escaneo local de carpetas...")
    print("[ALDIMI] Carpeta DNI_ALDIMI:", Path("DNI_ALDIMI").resolve())
    print("[ALDIMI] Carpeta LAB_ALDIMI:", Path("LAB_ALDIMI").resolve())

    resultados = sincronizar_carpetas(max_images=max_images)

    print("[ALDIMI] Escaneo local finalizado.")
    print(f"         Imágenes procesadas: {resultados['procesados']}")
    print(f"         Detalles registrados: {len(resultados['resultados'])}")
    return resultados


def main() -> None:
    max_images_env = os.environ.get("ALDIMI_MAX_IMAGES", "1")
    try:
        max_images = int(max_images_env)
    except Exception:
        max_images = 1

    ejecutar_local(max_images=max_images)


if __name__ == "__main__":
    main()
