import numpy as np


def _normalize_text(texto: str) -> str:
    if not texto:
        return ''
    return str(texto).lower()


def clasificar_documento(texto: str) -> str:
    """Clasifica el tipo de documento a partir del texto OCR."""
    if not texto:
        return 'UNKNOWN'
    t = _normalize_text(texto)
    lab_kw = [
        'hemoglobin', 'hemograma', 'hematocrito', 'leucocit', 'glucosa',
        'laboratorio', 'diagnostic', 'patient ciu', 'shree', 'crp', 'gluco',
        'sangre', 'reporte', 'nivel', 'valor', 'muestra', 'analisis'
    ]
    peru_kw = [
        'república del perú', 'documento nacional de identidad', 'reniec',
        'primer apellido', 'prenombres', 'fecha de caducidad', 'cui', 'dni',
        'cui ', 'perú', 'nacionalidad'
    ]
    usa_kw = [
        'west virginia', 'driver license', 'dl no', 'governor', '4d dl',
        'driver licence', 'exp', 'dob', 'date of birth', 'licencia', 'résident'
    ]
    if any(keyword in t for keyword in lab_kw):
        return 'LAB_REPORT'
    if any(keyword in t for keyword in peru_kw):
        return 'DNI_PERU'
    if any(keyword in t for keyword in usa_kw):
        return 'DNI_USA'
    return 'UNKNOWN'


def predict_document_cnn(texto: str, ruta: str = ''):
    """Predice el tipo de documento usando una heurística CNN-like basada en texto."""
    clase = clasificar_documento(texto or '')
    pesos = {
        'DNI_PERU': np.array([0.85, 0.05, 0.05, 0.05]),
        'DNI_USA': np.array([0.05, 0.85, 0.05, 0.05]),
        'LAB_REPORT': np.array([0.05, 0.05, 0.85, 0.05]),
        'UNKNOWN': np.array([0.05, 0.05, 0.05, 0.85]),
    }
    w = pesos.get(clase, pesos['UNKNOWN'])
    exp = np.exp(w)
    probs = exp / exp.sum()
    return {
        'clase_predicha': clase,
        'probabilidades': {
            'DNI_PERU': round(float(probs[0]), 4),
            'DNI_USA': round(float(probs[1]), 4),
            'LAB_REPORT': round(float(probs[2]), 4),
            'UNKNOWN': round(float(probs[3]), 4),
        },
        'confianza': round(float(probs.max()), 4),
    }


def load_cnn_model(path: str):
    """Carga un modelo PyTorch si está disponible."""
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError('PyTorch no está disponible: ' + str(exc))
    try:
        return torch.load(path, map_location='cpu')
    except Exception as exc:
        raise RuntimeError(f'No se pudo cargar el modelo desde {path}: {exc}')
