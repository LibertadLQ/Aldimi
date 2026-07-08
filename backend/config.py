# -*- coding: utf-8 -*-
"""Configuración global de ALDIMI - MÓDIFICA AQUÍ EL LÍMITE DE ESCANEO"""

# ════════════════════════════════════════════════════════════════════════════════
#  CAMBIAR AQUÍ: Límite de archivos a escanear (1-100, donde 100 = todos)
# ════════════════════════════════════════════════════════════════════════════════
SCAN_LIMIT = 4  


# Los demás valores se derivan automáticamente de SCAN_LIMIT
MAX_SCAN_LIMIT = 100
DEFAULT_SCAN_LIMIT = SCAN_LIMIT


def get_scan_limit() -> int:
    """Devuelve el límite de escaneo configurado (1-100)."""
    import os
    env_limit = os.environ.get("ALDIMI_MAX_IMAGES")
    if env_limit:
        try:
            val = int(str(env_limit).strip())
            if 1 <= val <= MAX_SCAN_LIMIT:
                return val
        except Exception:
            pass
    return SCAN_LIMIT
