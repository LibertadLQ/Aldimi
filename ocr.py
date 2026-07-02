# ocr.py
# Compat wrapper: exporta la aplicación FastAPI desde main_local (dev) o main (prod)
try:
    from main_local import app
    source = 'main_local'
except Exception:
    try:
        from main import app
        source = 'main'
    except Exception:
        app = None
        source = None

if app is None:
    raise ImportError('No se encontró una app FastAPI en main_local.py ni en main.py')

__all__ = ['app']
