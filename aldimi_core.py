# aldimi_core.py — Proxy for the unified aldimi module
# Supports both local (Tesseract+EasyOCR) and production (EasyOCR only) modes
# via ALDIMI_ENV environment variable

import aldimi as _core

# Re-export all public functions and database objects
from aldimi import (
    # NLP functions
    chatbot_response_nlp,
    preprocess_text,
    detect_intent,
    buscar_faq_reglamento,
    
    # OCR functions
    procesar_imagen_dni,
    procesar_imagen_lab,
    _fmt_lab_resultado,
    _extraer_texto_imagen,
    clasificar_documento,
    extraer_ciu,
    
    # Database functions
    registrar_paciente,
    listar_pacientes,
    listar_alertas,
    cargar_bd,
    guardar_bd,
    
    # Database object
    _BD,
    
    # Configuration
    ALDIMI_ENV,
    _USE_TESSERACT,
)

__all__ = [
    'chatbot_response_nlp', 'preprocess_text', 'detect_intent', 'buscar_faq_reglamento',
    'procesar_imagen_dni', 'procesar_imagen_lab', '_fmt_lab_resultado',
    '_extraer_texto_imagen', 'clasificar_documento', 'extraer_ciu',
    'registrar_paciente', 'listar_pacientes', 'listar_alertas',
    'cargar_bd', 'guardar_bd', '_BD', 'ALDIMI_ENV', '_USE_TESSERACT',
]
