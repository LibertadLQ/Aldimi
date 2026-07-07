"""Pequeño wrapper para uso local — reemplazo del notebook ALDIMI_Core_AI.ipynb.

Proporciona utilidades que integran `expediente` y `db` para uso desde
la línea de comandos o desde `backend/main.py` durante desarrollo.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from .expediente import sincronizar_carpetas
from .db import cargar_bd, guardar_bd


def ejecutar_local_scan(max_images: int = 0) -> Dict[str, Any]:
    """Escanea `DNI_ALDIMI` y `LAB_ALDIMI` localmente.

    Parámetro `max_images` aplicado tanto a DNI como a LAB (pruebas rápidas).
    Devuelve el resultado tal como lo entrega `sincronizar_carpetas`.
    """
    resultados = sincronizar_carpetas(max_images_dni=max_images, max_images_lab=max_images)
    try:
        procesados = resultados.get("procesados", 0)
    except Exception:
        procesados = 0
    print(f"Escaneo local completado: {procesados} imágenes procesadas")
    return resultados


def consultar_expediente(ciu: str) -> Optional[dict]:
    """Carga y muestra por consola el expediente de un paciente por `ciu`.

    Devuelve `None` si no existe.
    """
    ciu = str(ciu).strip().upper()
    bd = cargar_bd()
    registro = bd.get(ciu) if isinstance(bd, dict) else None
    if registro is None:
        print(f"No encontrado: {ciu}")
    else:
        print(f"Expediente {ciu}:")
        print(registro)
    return registro


if __name__ == "__main__":
    # Ejecución rápida desde la línea de comandos para pruebas locales
    print("ALDIMI code_ALDIMI ejecutando una prueba rápida...")
    print("Carpeta raíz:", Path.cwd().resolve())
    ejecutar_local_scan(max_images=1)




