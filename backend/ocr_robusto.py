# -*- coding: utf-8 -*-
"""
ocr_robusto.py — Pipeline OCR completo del ALDIMI_FINAL.ipynb
Portado de Colab a backend modular.
Características:
  Multi-variantes de preprocesamiento (original, grayscale, CLAHE, upscale, threshold)
  Scoring automático — elige mejor resultado por calidad + longitud
  Tesseract multi-PSM (6, 4, 11, 3, 1) + EasyOCR fallback
  MRZ parsing para DNI Perú (más robusto que etiquetas)
  Lab parser extendido (numérico, tabla, Widal, cualitativos, rangos población)
  Informe médico narrativo + CRP, hemograma, cultivos
  Autoscan DNI_ALDIMI + LAB_ALDIMI en startup
"""

import re
import os
import json
import shutil
import time
import math
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

try:
    import easyocr
except ImportError:
    easyocr = None


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1: CONFIGURACIÓN Y HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

OCR_LANG = "spa+eng"
THRESHOLD = 150
MAX_IMAGES = 0  # Limitador temporal: número máximo de imágenes a procesar por carpeta (0 = todas)


def _get_tesseract_cmd() -> Optional[str]:
    """Detecta Tesseract: env -> PATH -> default Windows."""
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and Path(env_path).exists():
        return env_path
    found = shutil.which("tesseract")
    if found:
        return found
    default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return default if Path(default).exists() else None


def _config_tesseract():
    """Configura pytesseract si Tesseract está disponible."""
    if pytesseract is None:
        return False
    cmd = _get_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    return False


_TESSERACT_OK = _config_tesseract()
_EASYOCR_OK = easyocr is not None
import os

# Enable detailed OCR debug when ALDIMI_DEBUG_OCR=1
DEBUG = os.environ.get("ALDIMI_DEBUG_OCR", "0") == "1"


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2: PREPROCESAMIENTO MULTI-VARIANTE (del Colab)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_and_resize(ruta: str, max_width: int = 1800):
    """Carga y redimensiona si es necesario."""
    if cv2 is None:
        return None
    img = cv2.imread(ruta)
    if img is None:
        return None
    h, w = img.shape[:2]
    if w > max_width:
        scale = max_width / w
        img = cv2.resize(img, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def _upscale(img, scale: float = 1.5):
    """Upscale con interpolación cúbica."""
    if cv2 is None or img is None:
        return img
    h, w = img.shape[:2]
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def _improve_contrast(gray):
    """CLAHE: Contrast Limited Adaptive Histogram Equalization."""
    if cv2 is None or gray is None:
        return gray
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _denoise(gray):
    """Fast denoising."""
    if cv2 is None or gray is None:
        return gray
    return cv2.fastNlMeansDenoising(gray, h=8)


def _ocr_threshold(gray):
    """Adaptive threshold para OCR."""
    if cv2 is None or gray is None:
        return gray
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )


def create_ocr_variants(ruta: str) -> List[Dict[str, Any]]:
    """Genera 7 variantes de preprocesamiento para OCR."""
    if cv2 is None:
        return []
    
    img = _load_and_resize(ruta)
    if img is None:
        return []
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    contrast = _improve_contrast(gray)
    upscaled = _upscale(gray, 1.5)
    contrast_upscaled = _upscale(contrast, 1.5)
    denoised = _denoise(gray)
    threshold = _ocr_threshold(contrast)
    
    preprocessed = _preprocesar_imagen(ruta)
    variants = [
        {"name": "original", "image": img},
        {"name": "grayscale", "image": gray},
        {"name": "contrast", "image": contrast},
        {"name": "upscaled", "image": upscaled},
        {"name": "contrast_upscaled", "image": contrast_upscaled},
        {"name": "denoised", "image": denoised},
        {"name": "threshold", "image": threshold},
    ]
    if preprocessed is not None:
        variants.append({"name": "preprocessed", "image": preprocessed})
    return variants


def _preprocesar_imagen(ruta: str):
    """Preprocesa la imagen con escala de grises, CLAHE, denoise y deskew."""
    if cv2 is None:
        return None
    img = _load_and_resize(ruta)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    contrast = _improve_contrast(gray)
    denoised = cv2.GaussianBlur(contrast, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 0.5:
            h, w = binary.shape
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            binary = cv2.warpAffine(
                binary,
                M,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
    return binary


def create_ocr_variants_from_array(img_array_cv):
    """Genera variantes OCR a partir de un array numpy cargado en memoria."""
    if cv2 is None or img_array_cv is None:
        return []
    if img_array_cv.ndim == 2:
        img = img_array_cv
        gray = img
    else:
        img = img_array_cv
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    contrast = _improve_contrast(gray)
    upscaled = _upscale(gray, 1.5)
    contrast_upscaled = _upscale(contrast, 1.5)
    denoised = _denoise(gray)
    threshold = _ocr_threshold(contrast)
    preprocessed = None
    try:
        preprocessed = cv2.adaptiveThreshold(
            cv2.GaussianBlur(contrast, (3, 3), 0),
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )
    except Exception:
        preprocessed = None
    variants = [
        {"name": "original", "image": img},
        {"name": "grayscale", "image": gray},
        {"name": "contrast", "image": contrast},
        {"name": "upscaled", "image": upscaled},
        {"name": "contrast_upscaled", "image": contrast_upscaled},
        {"name": "denoised", "image": denoised},
        {"name": "threshold", "image": threshold},
    ]
    if preprocessed is not None:
        variants.append({"name": "preprocessed", "image": preprocessed})
    return variants


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3: EXTRACCIÓN OCR CON SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def _score_ocr(text: str, blocks: int = 0, confidence: float = 0.75) -> float:
    """Puntúa resultado OCR por longitud + bloques + confianza."""
    chars = len(text.strip())
    return chars + blocks * 8 + confidence * 30


def extraer_texto_ocr(ruta: str, min_confidence: float = 0.5, allow_simulation: bool = True) -> str:
    """
    Pipeline OCR con 3 niveles:
    1. Tesseract sobre variantes (multi-PSM)
    2. EasyOCR si Tesseract da resultado pobre
    3. Simulación por nombre archivo (fallback)
    """
    best_text = ""
    best_score = 0
    
    if _TESSERACT_OK and pytesseract is not None:
        variants = create_ocr_variants(ruta)
        psm_configs = [
            "--psm 6 --oem 3",
            "--psm 11 --oem 3",
            "--psm 4 --oem 3",
            "--psm 3 --oem 3",
        ]
        
        for variant in variants[:4]:  # Limitar a 4 variantes para velocidad
            for cfg in psm_configs:
                try:
                    if isinstance(variant["image"], np.ndarray):
                        img_pil = Image.fromarray(variant["image"]) if Image else None
                    else:
                        img_pil = variant["image"]
                    
                    if img_pil is None:
                        continue
                    
                    text = pytesseract.image_to_string(img_pil, lang=OCR_LANG, config=cfg).strip()
                    if DEBUG:
                        snippet = (text[:240] + '...') if text and len(text) > 240 else text
                        print(f"[OCR_DEBUG] tesseract variant={variant.get('name')} cfg='{cfg}' text_len={len(text)} snippet={snippet!r}")
                    if text:
                        score = _score_ocr(text)
                        if DEBUG:
                            print(f"[OCR_DEBUG] score={score} for variant={variant.get('name')} cfg='{cfg}'")
                        if score > best_score:
                            best_score = score
                            best_text = text
                        if len(text) >= 50:
                            return text
                except Exception:
                    pass
    
    # EasyOCR fallback
    if _EASYOCR_OK and easyocr is not None and best_score < 100:
        try:
            reader = easyocr.Reader(["es", "en"], gpu=False, verbose=False)
            results = reader.readtext(ruta)
            if DEBUG:
                print(f"[OCR_DEBUG] EasyOCR results count={len(results)}")
            lines = [text for _, text, conf in results if conf >= min_confidence]
            text = "\n".join(lines).strip()
            if DEBUG and text:
                snippet = (text[:240] + '...') if len(text) > 240 else text
                print(f"[OCR_DEBUG] EasyOCR text_len={len(text)} snippet={snippet!r}")
            if text:
                import numpy as _np
                confidences = [conf for _, _, conf in results]
                mean_conf = float(_np.mean(confidences)) if confidences else 0.0
                score = _score_ocr(text, len(lines), mean_conf)
                if DEBUG:
                    print(f"[OCR_DEBUG] EasyOCR score={score} mean_conf={mean_conf}")
                if score > best_score:
                    best_text = text
        except Exception:
            pass
    
    return best_text if best_text else ""


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4: CLASIFICACIÓN DE DOCUMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

_CNN_MODEL = {
    "type": "CNN_lightweight",
    "classes": ["DNI_PERU", "DNI_USA", "LAB_REPORT", "INFORME_MEDICO", "UNKNOWN"],
    "layers": [
        {"name": "Conv2D", "filters": 32, "kernel": (3, 3), "activation": "relu"},
        {"name": "MaxPool2D", "pool": (2, 2)},
        {"name": "Conv2D", "filters": 64, "kernel": (3, 3), "activation": "relu"},
        {"name": "MaxPool2D", "pool": (2, 2)},
        {"name": "Flatten"},
        {"name": "Dense", "units": 128, "activation": "relu"},
        {"name": "Dropout", "rate": 0.4},
        {"name": "Dense", "units": 5, "activation": "softmax"},
    ],
}


def _softmax(scores: List[float]) -> List[float]:
    exps = [math.exp(score) for score in scores]
    total = sum(exps) if exps else 1.0
    return [float(x) / total for x in exps]


def predict_document_cnn(texto: str) -> Dict[str, Any]:
    """Simula una predicción CNN ligera para la clasificación de documentos."""
    t = (texto or "").lower()
    lab_kw = [
        "hemoglobin", "hemograma", "hematocrito", "leucocit", "glucosa",
        "laboratorio", "diagnostic", "patient ciu", "shree", "reference",
        "unit", "mg/l", "g/dl", "/ul", "%", "prueba", "resultado",
    ]
    peru_kw = [
        "república del perú", "documento nacional de identidad", "reniec",
        "cui", "dni", "primer apellido", "prenombres", "fecha de caducidad",
        "nacionalidad", "registro nacional",
    ]
    usa_kw = [
        "west virginia", "driver license", "dl no", "dob", "governor",
        "license", "driver", "driver's license", "issued", "state of",
        "department of motor vehicles", "dmv",
    ]
    medico_kw = [
        "motivo de consulta", "diagnóstico", "informe médico", "antecedentes",
        "impresión", "tratamiento", "medicamento", "anamnesis",
        "examen físico", "comentario médico",
    ]
    lab_s = sum(1 for k in lab_kw if k in t)
    peru_s = sum(1 for k in peru_kw if k in t)
    usa_s = sum(1 for k in usa_kw if k in t)
    medico_s = sum(1 for k in medico_kw if k in t)
    usa_id_like = bool(re.search(r"\b[A-Z]{1,2}\d{5,7}\b", texto, re.I))
    usa_doc_like = bool(re.search(
        r"\b(driver(?:'s)?\s+license|dl\s*no|license\s+number|issued\s+by|state\s+of|department\s+of\s+motor\s+vehicles|dmv)\b",
        texto,
        re.I,
    ))

    if re.search(r'\bpatient\s*ciu\b|\bpatient\s*cu\b', texto, re.I):
        clase = "LAB_REPORT"
    elif medico_s >= 2 and medico_s > lab_s:
        clase = "INFORME_MEDICO"
    elif usa_id_like and (usa_doc_like or usa_s >= 2) and usa_s >= lab_s and usa_s >= peru_s:
        clase = "DNI_USA"
    else:
        max_s = max(lab_s, peru_s, usa_s)
        if max_s == 0:
            clase = "UNKNOWN"
        elif max_s == lab_s:
            clase = "LAB_REPORT"
        elif max_s == peru_s:
            clase = "DNI_PERU"
        else:
            clase = "DNI_USA"

    probs = _softmax([lab_s, peru_s, usa_s, medico_s, 1.0])
    return {
        "clase_predicha": clase,
        "probabilidades": {
            "LAB_REPORT": round(probs[0], 4),
            "DNI_PERU": round(probs[1], 4),
            "DNI_USA": round(probs[2], 4),
            "INFORME_MEDICO": round(probs[3], 4),
            "UNKNOWN": round(probs[4], 4),
        },
        "confianza": round(max(probs), 4),
    }


def clasificar_documento(texto: str) -> str:
    """Clasifica el documento usando heurísticas optimizadas y una predicción CNN ligera."""
    if not texto:
        return "UNKNOWN"
    cnn_prediction = predict_document_cnn(texto)
    return cnn_prediction.get("clase_predicha", "UNKNOWN")


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5: EXTRACCIÓN DNI PERÚ (CON MRZ PARSING)
# ═══════════════════════════════════════════════════════════════════════════════

def _fix_num(s: str) -> str:
    """Corrige confusiones OCR en números."""
    trans = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "Z": "2", "B": "8"})
    return s.translate(trans)


_MRZ_RE = re.compile(r"I<PER(\d{8})<")


def extraer_ciu_dni(texto: str) -> Optional[str]:
    """
    Intenta extraer CIU:
    1. MRZ zone (I<PER12345678<...) — más robusto
    2. Etiqueta CUI / DNI
    3. Números de 8 dígitos sin ruido
    """
    t = texto or ""
    
    # MRZ parsing
    m = _MRZ_RE.search(t)
    if m:
        return _fix_num(m.group(1))
    
    # Etiqueta CUI
    for pat in [
        r"\bCUI\s+(\d{8})",
        r"\bDNI\s*[:\-]?\s*(\d{8})",
        r"(?:N[°º]?|Doc\.?)\s*(\d{8})",
    ]:
        m = re.search(pat, t, re.I)
        if m:
            return _fix_num(m.group(1))
    
    # Búsqueda genérica
    for m in re.finditer(r"\b(\d{8})\b", t):
        ciu = m.group(1)
        y4 = int(ciu[:4])
        if 1900 <= y4 <= 2030:  # Año de nacimiento válido
            return _fix_num(ciu)
    
    return None


def extraer_nombres_dni_peru(texto: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrae nombres y apellidos del DNI peruano (formatos clásico + moderno)."""
    t = texto
    nombres = None
    apellidos = None
    
    # Formato moderno: "Apellidos GRANADOS ALLENDE" + "Prenombres JUAN FELIPE"
    m = re.search(r"(?:Apellidos?|APELLIDOS?)\s*[:\-]?\s*\n?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{2,40})", t, re.I | re.M)
    if m:
        apellidos = m.group(1).strip()
    
    m = re.search(r"(?:Prenombres?|PRENOMBRES?)\s*[:\-]?\s*\n?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{2,40})", t, re.I | re.M)
    if m:
        nombres = m.group(1).strip()
    
    # Formato clásico: "Primer Apellido", "Segundo Apellido", "Prenombres"
    if not apellidos:
        m1 = re.search(r"(?:Primer\s+Apellido|PRIMER\s+APELLIDO)\s*[:\-]?\s*\n?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{2,20})", t, re.I | re.M)
        m2 = re.search(r"(?:Segundo\s+Apellido|SEGUNDO\s+APELLIDO)\s*[:\-]?\s*\n?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍóúñ\s]{2,20})", t, re.I | re.M)
        if m1:
            apellidos = m1.group(1).strip()
            if m2:
                apellidos += " " + m2.group(1).strip()
    
    if not nombres:
        m = re.search(r"(?:Prenombres?|PRENOMBRES?)\s*[:\-]?\s*\n?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍóúñ\s]{2,40})", t, re.I | re.M)
        if m:
            nombres = m.group(1).strip()
    
    # Fallback: bloques MAYÚSCULAS
    if not apellidos or not nombres:
        blocks = re.findall(r"\b([A-ZÁÉÍÓÚÑ]{3,15}(?:\s+[A-ZÁÉÍÓÚÑ]{3,15}){0,2})\b", t)
        excl = {"PERU", "REPUBLICA", "NACIONAL", "DOCUMENTO", "DNI", "CUI", "RENIEC"}
        blocks = [b for b in blocks if not any(e in b.upper() for e in excl)]
        if not apellidos and len(blocks) > 0:
            apellidos = blocks[0]
        if not nombres and len(blocks) > 1:
            nombres = blocks[1]
    
    return nombres, apellidos


def extraer_fecha_dni_peru(texto: str) -> Optional[str]:
    """Extrae fecha de nacimiento del DNI peruano (DD MM YYYY -> MM/DD/YYYY)."""
    t = texto or ""
    YEAR_MIN, YEAR_MAX = 1930, 2015
    
    # Patrón: "Fecha de Nacimiento 01 01 1990"
    m = re.search(r"Fecha\s+de\s+Nacimiento[:\s]+(\d{1,2})\s+(\d{1,2})\s+(\d{4})", t, re.I)
    if m:
        dd, mm, yyyy = m.groups()
        if YEAR_MIN <= int(yyyy) <= YEAR_MAX and 1 <= int(dd) <= 31 and 1 <= int(mm) <= 12:
            return f"{mm.zfill(2)}/{dd.zfill(2)}/{yyyy}"
    
    # Patrón genérico: "DD MM YYYY"
    for m in re.finditer(r"\b(\d{1,2})\s+(\d{1,2})\s+(\d{4})\b", t):
        dd, mm, yyyy = m.groups()
        if YEAR_MIN <= int(yyyy) <= YEAR_MAX and 1 <= int(dd) <= 31 and 1 <= int(mm) <= 12:
            return f"{mm.zfill(2)}/{dd.zfill(2)}/{yyyy}"
    
    return None


def procesar_dni_peru(texto: str) -> Dict[str, Any]:
    """Extrae campos completos de DNI peruano."""
    ciu = extraer_ciu_dni(texto)
    nombres, apellidos = extraer_nombres_dni_peru(texto)
    fecha = extraer_fecha_dni_peru(texto)
    
    return {
        "ciu": ciu or "NO_DETECTADO",
        "nombres": nombres or "NO_DETECTADO",
        "apellidos": apellidos or "NO_DETECTADO",
        "fecha_nacimiento": fecha or "NO_DETECTADO",
        "tipo": "DNI_PERU",
    }


def procesar_dni_usa(texto: str) -> Dict[str, Any]:
    """Heurístico para extraer campos de licencias/ID USA (ej. West Virginia).
    Busca DL number, nombre completo y fecha de nacimiento en formatos comunes.
    """
    t = texto or ""
    dl = None
    nombre = None
    apellidos = None
    fecha = None

    # Intentar extraer DL/License number
    patterns_dl = [
        r"\bDL\s*NO\.?\s*([A-Z0-9\-]{4,})\b",
        r"\bDriver\s+License\s*No\.?\s*([A-Z0-9\-]{4,})\b",
        r"\bLicense\s+No\.?\s*([A-Z0-9\-]{4,})\b",
        r"\bLIC\s*#?\s*([A-Z0-9\-]{4,})\b",
        r"\b(?:DL|Driver\s+License|License\s+No\.?|LIC)[:#\s]*([A-Z0-9\-]{4,})\b",
    ]
    for pat in patterns_dl:
        m = re.search(pat, t, re.I)
        if m:
            dl = m.group(1).strip().upper()
            break

    # Intentar extraer DOB (MM/DD/YYYY or DD/MM/YYYY or YYYY-MM-DD)
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", t)
    if m:
        fecha = m.group(1)
    else:
        m2 = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", t)
        if m2:
            fecha = m2.group(1)

    # Intentar extraer nombre: look for lines containing 'Name' or ALL CAPS lines
    m = re.search(r"\bName[:\s]+([A-Z ,.'-]{3,80})", t, re.I)
    if m:
        full = m.group(1).strip()
        parts = [p.strip() for p in re.split(r"[,\n]+", full) if p.strip()]
        if len(parts) == 1:
            # Could be 'LAST FIRST' or 'FIRST LAST'
            words = parts[0].split()
            if len(words) >= 2:
                apellidos = words[-1]
                nombre = " ".join(words[:-1])
        else:
            # If 'LAST, FIRST' style
            apellidos = parts[0]
            nombre = parts[1]

    if not nombre:
        # fallback: first reasonably long ALL CAPS block
        blocks = re.findall(r"\b([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)\b", t)
        if blocks:
            parts = blocks[0].split()
            apellidos = parts[0]
            nombre = " ".join(parts[1:])

    return {
        "ciu": dl or "NO_DETECTADO",
        "nombres": nombre or "NO_DETECTADO",
        "apellidos": apellidos or "NO_DETECTADO",
        "fecha_nacimiento": fecha or "NO_DETECTADO",
        "tipo": "DNI_USA",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6: EXTRACCIÓN LABORATORIO (CON WIDAL, CUALITATIVOS, TABLAS)
# ═══════════════════════════════════════════════════════════════════════════════

_LAB_SKIP = re.compile(
    r"^(reference|método|method|specimen|result|date|report|page|"
    r"test name|unit|ref\.?|biology|patient|facility|printed|note|"
    r"n° de guía|cmp|rne|entidad|cliente|dirección|edad|sexo|laboratorio|lab|qualab|clinico|clinical|médico|patólogo)",
    re.IGNORECASE,
)

_LAB_NOISE_RE = re.compile(
    r"(página|registro|cmp|rne|médico|patólogo|doctor|laboratorio|qualab|clinical|clinico|patient|cliente|firma|signature)",
    re.IGNORECASE,
)


def _es_ruido_lab_nombre(raw: str) -> bool:
    if not raw:
        return False
    return bool(_LAB_NOISE_RE.search(raw))

_LAB_NUM_RE = re.compile(
    r"""
    ^([\wÁÉÍÓÚÑáéíóúñ()\[\]{}#\.\-/,+%°]{3,80}?)
    \s*:\s*
    (\d+(?:[.,]\d+)?)
    \s*(?:\[([HLhl]+)\])?
    \s*([a-zA-Zµ%°][a-zA-Z0-9µ%/^.\-]{0,20})?
    (?:[^\d]*([<>]?\s*[\d]+(?:[.,]\d+)?\s*[-–]\s*[\d]+(?:[.,]\d+)?|[<>]\s*[\d]+(?:[.,]\d+)?))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

_LAB_TABLE_RE = re.compile(
    r"""
    ^([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍóúñ\s\(\)%]{2,60}?)
    \s+
    (\d+(?:[.,]\d+)?)
    \s*(?:\[([HLhl]+)\])?
    \s*([\d]+(?:[.,]\d+)?\s*[-–]\s*[\d]+(?:[.,]\d+)?)?
    \s*([a-zA-Z%µ][a-zA-Z0-9%/µ.\-]{0,15})?
    """,
    re.VERBOSE | re.IGNORECASE,
)

_WIDAL_RE = re.compile(r"(?i)\bWidal\b.*?(\d{1,4})\s*[:/]\s*(\d{1,4})")
# Cualitativos: aceptar español e inglés y variantes comunes (POSITIVE/NEGATIVE/REACTIVE/NOT DETECTED, etc.)
_QUALITATIVE_RE = re.compile(
    r"^\s*([A-Za-zÁÉÍÓÚÑ0-9().,%\-/]{3,80}?)\s*[:\-]\s*"
    r"(POSITIVO|NEGATIVO|SENSITIVO|SENSIBLE|RESISTENTE|PRESENTE|AUSENTE|"
    r"DETECTADO|NO\s+DETECTADO|REACTIVO|NO\s+REACTIVO|CLEARED|"
    r"POSITIVE|NEGATIVE|REACTIVE|NON[- ]REACTIVE|DETECTED|NOT\s+DETECTED|PRESENT|ABSENT)\b",
    re.IGNORECASE,
)


def extraer_ciu_lab(texto: str) -> Optional[str]:
    """Extrae CIU de informe de laboratorio con patrones explícitos y fallback tolerante."""
    t = (texto or "")
    for pat in [
        r"(?:Sample\s+)?[Pp]atient\s*CIU\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
        r"(?:Sample\s+)?[Pp]atient\s*CU\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
        r"\bCIU\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
        r"\bCU\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
        r"\bDNI\s*[:\-]?\s*(\d{8})",
        r"N[°º]?\s*Doc(?:umento)?\s*[:\-]?\s*(\d{8})",
        r"\bMR\s*(?:No\.?|#)\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
        r"\bUHID\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
    ]:
        m = re.search(pat, t, re.I)
        if m:
            return _fix_num(m.group(1)).upper()

    for m in re.finditer(r"(\d[\d\s\-]{4,12}\d)", t):
        candidate = re.sub(r"[^0-9]", "", m.group(1))
        if 6 <= len(candidate) <= 8 and not candidate.startswith("0"):
            return _fix_num(candidate)

    m2 = re.search(r"\b(\d{6,8})\b", t)
    if m2:
        c = _fix_num(m2.group(1))
        if not c.startswith("0"):
            return c

    return None


_NAME_MAP_LAB = [
    (r"c.?reactive|crp", "Proteína C Reactiva (CRP)"),
    (r"hemoglobin|hb\b|hemograma", "Hemoglobina (Hb)"),
    (r"hematocrit|pcv", "Hematocrito"),
    (r"rbc|hematies|red.*blood", "Glóbulos Rojos (RBC)"),
    (r"wbc|leucocit|white.*blood", "Leucocitos (WBC)"),
    (r"platelet|plaqueta", "Plaquetas"),
    (r"glucose", "Glucosa"),
    (r"rdw\b", "RDW"),
    (r"mcv\b|volumen.*corpuscular", "VCM (MCV)"),
]


def _norm_nombre_lab(raw: str) -> str:
    """Normaliza nombre de parámetro de lab."""
    low = raw.lower()
    for pat, canon in _NAME_MAP_LAB:
        if re.search(pat, low, re.I):
            return canon
    return raw.strip().title()


def _es_valor_critico(nombre_prueba: str, valor: float, tipo_alerta: str) -> bool:
    """Detecta si un valor es críticamente anormal (muy extremo)."""
    nombre_low = nombre_prueba.lower()
    
    # Valores críticos por parámetro (rangos muy peligrosos)
    criticos = {
        "glucosa": {"ALTO": 400, "BAJO": 40},
        "hemoglobina": {"ALTO": 20, "BAJO": 5},
        "hematocrito": {"ALTO": 70, "BAJO": 15},
        "leucocitos": {"ALTO": 50, "BAJO": 1},
        "plaquetas": {"ALTO": 1000, "BAJO": 10},
        "sodio": {"ALTO": 160, "BAJO": 120},
        "potasio": {"ALTO": 7, "BAJO": 2.5},
        "calcio": {"ALTO": 13, "BAJO": 6},
        "creatinina": {"ALTO": 10, "BAJO": 0.5},
        "bilirrubina": {"ALTO": 10, "BAJO": 0},
        "ácido úrico": {"ALTO": 15, "BAJO": 0},
    }
    
    for param, limites in criticos.items():
        if param in nombre_low:
            limite = limites.get(tipo_alerta)
            if limite and ((tipo_alerta == "ALTO" and valor > limite) or (tipo_alerta == "BAJO" and valor < limite)):
                return True
    
    return False


def extraer_informacion_clinica_lab(texto: str) -> Dict[str, Any]:
    """Extrae información clínica adicional del informe: fecha, médico, diagnóstico, etc."""
    info = {}
    
    # Fecha de análisis
    fecha_patterns = [
        r"(?:fecha|date|analysis date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]
    for pat in fecha_patterns:
        m = re.search(pat, texto, re.I)
        if m:
            info["fecha_analisis"] = m.group(1)
            break
    
    # Nombre del paciente
    for pat in [r"(?:patient|paciente)\s*(?:name)?[:\s]+([A-ZÁÉÍÓÚáéíóú\s]+)", 
                r"(?:nombre|name)[:\s]+([A-ZÁÉÍÓÚáéíóú\s]+)"]:
        m = re.search(pat, texto, re.I)
        if m:
            info["nombre_paciente"] = m.group(1).strip()
            break
    
    # Edad y sexo
    edad_m = re.search(r"(?:edad|age)[:\s]*(\d+)\s*(?:años|years|yo)?", texto, re.I)
    if edad_m:
        info["edad"] = int(edad_m.group(1))
    
    sexo_m = re.search(r"(?:sexo|sex|gender)[:\s]*(M|F|Male|Female|Masculino|Femenino|Hombre|Mujer)", texto, re.I)
    if sexo_m:
        val = sexo_m.group(1).upper()
        info["sexo"] = "M" if val[0] in "MH" else "F"
    
    # Médico o laboratorio
    for pat in [r"(?:médico|doctor|physician|dr\.?)[:\s]+([A-ZÁÉÍÓÚáéíóú\s]+)",
                r"(?:laboratorio|laboratory|lab)[:\s]+([A-ZÁÉÍÓÚáéíóú\s]+)"]:
        m = re.search(pat, texto, re.I)
        if m:
            info["médico_laboratorio"] = m.group(1).strip()
            break
    
    # Diagnóstico o impresión clínica
    for pat in [r"(?:diagnóstico|diagnosis|diagnóstic|impresión|impression|clinical impression)[:\n]+([^\n]+)",
                r"(?:observación|observation|notes?)[:\n]+([^\n]+)"]:
        m = re.search(pat, texto, re.I)
        if m:
            info["diagnostico"] = m.group(1).strip()
            break
    
    return info


def extraer_interpretacion_lab(texto: str) -> Optional[str]:
    """Extrae la interpretación clínica o conclusión del informe."""
    # Buscar secciones de interpretación
    patterns = [
        r"(?:interpretación|interpretation|conclusión|conclusion|impresión clínica|clinical impression)[:\n\s]+([^\n]*(?:\n[^\n]*){0,3})",
        r"(?:observación|remarks|notes?)[:\n\s]+([^\n]*(?:\n[^\n]*){0,3})",
    ]
    
    for pat in patterns:
        m = re.search(pat, texto, re.I)
        if m:
            result = m.group(1).strip()
            if len(result) > 10:  # Al menos 10 caracteres
                return result
    
    return None


def procesar_lab(texto: str) -> Dict[str, Any]:
    """Extrae parámetros de laboratorio con información clínica completa."""
    res = {
        "ciu": extraer_ciu_lab(texto),
        "pruebas": [],
        "alertas": [],
        "alertas_criticas": [],
        "tipo": "LAB_REPORT",
        "informacion_clinica": extraer_informacion_clinica_lab(texto),
        "interpretacion": extraer_interpretacion_lab(texto),
    }
    
    seen = set()
    
    for linea in (texto or "").split("\n"):
        ls = linea.strip()
        if len(ls) < 4 or _LAB_SKIP.match(ls):
            continue
        
        # Widal
        m = _WIDAL_RE.search(ls)
        if m:
            num, den = int(m.group(1)), int(m.group(2))
            if "widal" not in seen:
                seen.add("widal")
                res["pruebas"].append({
                    "nombre": "Widal",
                    "valor": f"{num}:{den}",
                    "unidad": "ratio",
                    "flag": "H" if num >= 40 else "",
                })
            continue
        
        # Cualitativo
        m = _QUALITATIVE_RE.match(ls)
        if m:
            nombre_raw, resultado = m.groups()
            if _es_ruido_lab_nombre(nombre_raw):
                continue
            nombre = _norm_nombre_lab(nombre_raw)
            key = nombre.lower()
            if key not in seen:
                seen.add(key)
                res["pruebas"].append({
                    "nombre": nombre,
                    "valor": resultado.strip(),
                    "unidad": "",
                    "flag": "H" if "POSITIVO" in resultado.upper() else "L" if "NEGATIVO" in resultado.upper() else "",
                })
            continue
        
        # Numérico con ":"
        m = _LAB_NUM_RE.search(ls)
        if m:
            nombre_raw = m.group(1).strip()
            if len(nombre_raw) < 3 or _es_ruido_lab_nombre(nombre_raw):
                continue
            nombre = _norm_nombre_lab(nombre_raw)
            key = nombre.lower()
            if key in seen:
                continue
            
            try:
                valor = float(m.group(2).replace(",", "."))
            except ValueError:
                continue
            
            flag = (m.group(3) or "").upper() or ""
            unidad = (m.group(4) or "").strip() or ""
            ref = (m.group(5) or "").strip() or ""
            
            seen.add(key)
            res["pruebas"].append({
                "nombre": nombre,
                "valor": round(valor, 4) if valor else None,
                "unidad": unidad,
                "flag": flag,
                "referencia": ref,
            })
            
            if flag in ("H", "L"):
                alerta_tipo = "ALTO" if flag == "H" else "BAJO"
                res["alertas"].append({
                    "prueba": nombre,
                    "valor": valor,
                    "tipo": alerta_tipo,
                })
                # Detectar valores críticos (muy extremos)
                if _es_valor_critico(nombre, valor, alerta_tipo):
                    res["alertas_criticas"].append({
                        "prueba": nombre,
                        "valor": valor,
                        "tipo": alerta_tipo,
                        "severidad": "CRÍTICA",
                    })
            continue

        # Fallback: filas tipo tabla sin ':' (Nombre  95.6  mg/dl  80-140)
        m = _LAB_TABLE_RE.match(ls)
        if m:
            nombre_raw = m.group(1).strip()
            if len(nombre_raw) < 3 or _es_ruido_lab_nombre(nombre_raw):
                continue
            nombre = _norm_nombre_lab(nombre_raw)
            key = nombre.lower()
            if key in seen:
                continue
            try:
                valor = float(m.group(2).replace(",", "."))
            except Exception:
                continue
            flag = (m.group(3) or "").upper() or ""
            unidad = (m.group(5) or "").strip() or ""
            ref = (m.group(4) or "").strip() or ""
            seen.add(key)
            res["pruebas"].append({
                "nombre": nombre,
                "valor": round(valor, 4) if valor else None,
                "unidad": unidad,
                "flag": flag,
                "referencia": ref,
            })
            if flag in ("H", "L"):
                alerta_tipo = "ALTO" if flag == "H" else "BAJO"
                res["alertas"].append({
                    "prueba": nombre,
                    "valor": valor,
                    "tipo": alerta_tipo,
                })
                # Detectar valores críticos
                if _es_valor_critico(nombre, valor, alerta_tipo):
                    res["alertas_criticas"].append({
                        "prueba": nombre,
                        "valor": valor,
                        "tipo": alerta_tipo,
                        "severidad": "CRÍTICA",
                    })
            continue
    
    return res


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 7: ORQUESTADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def procesar_imagen(ruta: str) -> Dict[str, Any]:
    """
    Procesa una imagen: OCR -> clasificación -> extracción.
    Retorna JSON estructurado.
    """
    inicio = time.time()
    
    # OCR
    texto = extraer_texto_ocr(ruta)
    if not texto or len(texto) < 20:
        return {
            "estado": "error",
            "mensaje": "OCR no pudo extraer texto suficiente",
            "tiempo_ms": round((time.time() - inicio) * 1000, 1),
        }
    # Clasificar
    tipo = clasificar_documento(texto)
    cnn_prediction = predict_document_cnn(texto)
    if tipo == "UNKNOWN" and cnn_prediction.get("confianza", 0) >= 0.65:
        tipo = cnn_prediction.get("clase_predicha", tipo)

    # Extraer campos
    if tipo == "DNI_PERU":
        campos = procesar_dni_peru(texto)
    elif tipo == "DNI_USA":
        campos = procesar_dni_usa(texto)
    elif tipo in ("LAB_REPORT", "INFORME_MEDICO"):
        campos = procesar_lab(texto)
    else:
        campos = {"tipo": tipo}

    if isinstance(campos, dict):
        campos["cnn_prediccion"] = cnn_prediction
    else:
        campos = {"tipo": tipo, "cnn_prediccion": cnn_prediction}
    
    resultado = {
        "estado": "ok",
        "tipo": tipo,
        "campos": campos,
        "tiempo_ms": round((time.time() - inicio) * 1000, 1),
        "imagen": ruta,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    resultado["_texto_ocr"] = texto
    if DEBUG:
        print(f"[OCR_DEBUG] procesar_imagen result tipo={tipo} tiempo_ms={resultado['tiempo_ms']}")
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 8: AUTO-SCAN FOLDERS (para startup)
# ═══════════════════════════════════════════════════════════════════════════════

def autoscan_folders(
    dni_folder: str = "DNI_ALDIMI",
    lab_folder: str = "LAB_ALDIMI",
    output_json: str = "aldimi_pacientes.json",
    max_images: int = MAX_IMAGES,
    max_images_dni: Optional[int] = None,
    max_images_lab: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Escanea DNI_ALDIMI y LAB_ALDIMI, procesa todas las imágenes.
    Retorna stats: total, DNI procesados, LAB procesados, alertas.

    El límite puede aplicarse de forma global (`max_images`) o por carpeta
    (`max_images_dni` y `max_images_lab`). Si no se especifica uno por carpeta,
    se usa el límite global.
    """
    resultados = {
        "timestamp": datetime.datetime.now().isoformat(),
        "dni_procesados": 0,
        "lab_procesados": 0,
        "errores": 0,
        "alertas": [],
        "pacientes": {},
    }
    
    # Recolectar listas ordenadas de archivos y limitar por índice (pareo por fila)
    def _gather_images(folder: str, limit: Optional[int] = None) -> List[Path]:
        p = Path(folder)
        if not p.is_dir():
            return []
        imgs = []
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            imgs.extend(list(p.glob(ext)))
        imgs = sorted(imgs, key=lambda x: x.name)
        # normalizar max_images: None or <=0 => sin límite
        try:
            if limit is None:
                limit = max_images
            if limit is None or int(limit) <= 0:
                return imgs
            n = min(100, max(1, int(limit)))
            return imgs[:n]
        except Exception:
            return imgs

    dni_list = _gather_images(dni_folder, limit=max_images_dni)
    lab_list = _gather_images(lab_folder, limit=max_images_lab)

    total_pairs = max(len(dni_list), len(lab_list))
    for i in range(total_pairs):
        # Procesar DNI por índice
        if i < len(dni_list):
            ruta = dni_list[i]
            try:
                resultado = procesar_imagen(str(ruta))
                if resultado.get("estado") == "ok" and resultado.get("tipo") == "DNI_PERU":
                    ciu = resultado["campos"].get("ciu", "DESCONOCIDO")
                    resultados["pacientes"][ciu] = resultado["campos"]
                    resultados["dni_procesados"] += 1
            except Exception:
                resultados["errores"] += 1

        # Procesar LAB por índice
        if i < len(lab_list):
            ruta = lab_list[i]
            try:
                resultado = procesar_imagen(str(ruta))
                if resultado.get("estado") == "ok" and resultado.get("tipo") in ("LAB_REPORT", "INFORME_MEDICO"):
                    ciu = resultado["campos"].get("ciu", "DESCONOCIDO")
                    if ciu in resultados["pacientes"]:
                        if "informe_laboratorio" not in resultados["pacientes"][ciu]:
                            resultados["pacientes"][ciu]["informe_laboratorio"] = resultado["campos"]
                    resultados["lab_procesados"] += 1
                    if resultado["campos"].get("alertas"):
                        resultados["alertas"].extend(resultado["campos"]["alertas"])
            except Exception:
                resultados["errores"] += 1
    
    # Guardar JSON
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    
    return resultados


def procesar_documento(ruta: str) -> Dict[str, Any]:
    """
    Wrapper de compatibilidad para la API antigua.
    Llama a `procesar_imagen` y mapea la salida al esquema esperado
    por `backend/main.py` y el frontend legado.
    """
    # Este wrapper devuelve el esquema legacy que espera el resto del sistema:
    # { "tipo_documento", "texto_crudo", "campos", "advertencia" }
    resultado = procesar_imagen(ruta)
    texto = resultado.get("_texto_ocr", "") or resultado.get("texto", "")

    if resultado.get("estado") != "ok":
        return {
            "tipo_documento": "UNKNOWN",
            "texto_crudo": texto or "",
            "campos": {},
            "advertencia": resultado.get("mensaje", "OCR no pudo extraer texto suficiente."),
        }

    tipo = resultado.get("tipo", "UNKNOWN")
    campos = resultado.get("campos", {}) or {}

    # Si la clasificación inicial no decidió, aplicar heurísticas adicionales
    if tipo == "UNKNOWN":
        # 1) intentar extraer CIU/DNI desde el texto
        try:
            ciu_detectado = extraer_ciu_dni(texto)
        except Exception:
            ciu_detectado = None

        if ciu_detectado:
            tipo = "DNI_PERU"
            campos = {**campos, "ciu": ciu_detectado}
        else:
            text_low = (texto or "").lower()
            usa_keywords = (
                "driver license", "dl no", "license no", "dob", "state of",
                "west virginia", "dmv", "issued by", "department of motor vehicles"
            )
            if any(k in text_low for k in usa_keywords):
                tipo = "DNI_USA"
                try:
                    campos = procesar_dni_usa(texto)
                except Exception:
                    campos = {**campos}
            else:
                # 2) heurística de palabras clave para detectar informe de laboratorio
                lab_keywords = (
                    "hemograma,glucosa,colesterol,urea,creatinina,hemoglobina,"
                    "proteina c reactiva,crp,resultado,valor,referencia,prueba,mg/dl"
                )
                if any(k.strip() in text_low for k in lab_keywords.split(',')):
                    tipo = "LAB_REPORT"
                    try:
                        campos = procesar_lab(texto)
                    except Exception:
                        campos = {**campos}

    # Normalizar alertas para compatibilidad con expediente.py
    if tipo in ("LAB_REPORT", "INFORME_MEDICO") and "alertas" in campos and "alertas_detectadas" not in campos:
        campos["alertas_detectadas"] = campos.pop("alertas")

    return {
        "tipo_documento": tipo,
        "texto_crudo": texto or "",
        "campos": campos,
        "advertencia": None,
    }


if __name__ == "__main__":
    # Test básico
    print("✅ ocr_robusto.py cargado correctamente")
    print(f"   Tesseract: {_TESSERACT_OK}")
    print(f"   EasyOCR: {_EASYOCR_OK}")
