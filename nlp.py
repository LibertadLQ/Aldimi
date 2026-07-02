# nlp.py
# Compat wrapper: re-exporta funciones del módulo unificado `aldimi` para compatibilidad.
from aldimi import *

__all__ = [name for name in globals() if not name.startswith('_')]
