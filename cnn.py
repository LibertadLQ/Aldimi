import os
import importlib

env = os.environ.get('ALDIMI_ENV', 'local').lower()
module_name = 'aldimi_web' if env in ('prod', 'production') else 'aldimi_web_local'
_module = importlib.import_module(module_name)

# Reexportar funciones de procesamiento de imagen (OCR / CNN)
def procesar_imagen_dni(path):
    return _module.procesar_imagen_dni(path)

def procesar_imagen_lab(path, ciu_hint=""):
    # Firma compatible con aldimi_web_local / aldimi_web
    try:
        return _module.procesar_imagen_lab(path, ciu_hint=ciu_hint)
    except TypeError:
        # fallback: some versions may expect only (path) or (path, ciu_hint)
        return _module.procesar_imagen_lab(path, ciu_hint)

# Exponer módulo subyacente por si se necesita acceso directo
__all__ = ['procesar_imagen_dni', 'procesar_imagen_lab', '_module']
