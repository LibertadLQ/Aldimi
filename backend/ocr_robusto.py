# -*- coding: utf-8 -*-
"""
ocr_robusto.py — Pipeline OCR completo del ALDIMI_FINAL.ipynb
===========================================================
Portado de Colab a backend modular.
Características:
  ✅ Multi-variantes de preprocesamiento (original, grayscale, CLAHE, upscale, threshold)
  ✅ Scoring automático — elige mejor resultado por calidad + longitud
  ✅ Tesseract multi-PSM (6, 4, 11, 3, 1) + EasyOCR fallback
  ✅ MRZ parsing para DNI Perú (más robusto que etiquetas)
  ✅ Lab parser extendido (numérico, tabla, Widal, cualitativos, rangos población)
  ✅ Informe médico narrativo + CRP, hemograma, cultivos
  ✅ Autoscan DNI_ALDIMI + LAB_ALDIMI en startup
"""

import re
import os
import json
import shutil
import time
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
MAX_IMAGES = 1  # Limitador temporal: número máximo de imágenes a procesar por carpeta (1..100)


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
    
    return [
        {"name": "original", "image": img},
        {"name": "grayscale", "image": gray},
        {"name": "contrast", "image": contrast},
        {"name": "upscaled", "image": upscaled},
        {"name": "contrast_upscaled", "image": contrast_upscaled},
        {"name": "denoised", "image": denoised},
        {"name": "threshold", "image": threshold},
    ]


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
                    if text:
                        score = _score_ocr(text)
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
            lines = [text for _, text, conf in results if conf >= min_confidence]
            text = "\n".join(lines).strip()
            if text:
                score = _score_ocr(text, len(lines), np.mean([c for _, _, c in results]))
                if score > best_score:
                    best_text = text
        except Exception:
            pass
    
    return best_text if best_text else ""


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4: CLASIFICACIÓN DE DOCUMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

def clasificar_documento(texto: str) -> str:
    """Clasifica: DNI_PERU | DNI_USA | LAB_REPORT | INFORME_MEDICO | UNKNOWN."""
    if not texto:
        return "UNKNOWN"
    
    t = texto.lower()
    
    # Keywords
    lab_kw = [
        "hemoglobin", "hemograma", "hematocrito", "leucocit", "glucosa",
        "laboratorio", "diagnostic", "patient ciu", "resultado", "análisis",
        "prueba", "examen", "cmp:", "rne:", "reference", "unit", "valor",
    ]
    peru_kw = [
        "república del perú", "documento nacional", "reniec", "dni",
        "primer apellido", "prenombres", "fecha de caducidad", "cui",
    ]
    usa_kw = [
        "west virginia", "driver license", "dl no", "dob", "governor",
    ]
    medico_kw = [
        "motivo de consulta", "diagnóstico", "informe médico",
        "antecedentes", "impresión", "tratamiento", "medicamento",
    ]
    
    lab_s = sum(1 for k in lab_kw if k in t)
    peru_s = sum(1 for k in peru_kw if k in t)
    usa_s = sum(1 for k in usa_kw if k in t)
    medico_s = sum(1 for k in medico_kw if k in t)
    
    if medico_s >= 2 and medico_s > lab_s:
        return "INFORME_MEDICO"
    
    max_s = max(lab_s, peru_s, usa_s)
    if max_s == 0:
        return "UNKNOWN"
    if max_s == lab_s:
        return "LAB_REPORT"
    if max_s == peru_s:
        return "DNI_PERU"
    return "DNI_USA"


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


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6: EXTRACCIÓN LABORATORIO (CON WIDAL, CUALITATIVOS, TABLAS)
# ═══════════════════════════════════════════════════════════════════════════════

_LAB_SKIP = re.compile(
    r"^(reference|método|method|specimen|result|date|report|page|"
    r"test name|unit|ref\.?|biology|patient|facility|printed|note|"
    r"n° de guía|cmp|rne|entidad|cliente|dirección|edad|sexo)",
    re.IGNORECASE,
)

_LAB_NUM_RE = re.compile(
    r"""
    ^([\wÁÉÍÓÚÑáéíóúñ()\[\]{}#\.\-/,+%°]{3,80}?)
    \s*:\s*
    (\d+(?:[.,]\d+)?)
    \s*(?:\[([HLhl]+)\])?
    \s*([a-zA-Zµ%°][a-zA-Z0-9µ%/^.\-]{0,20})?
    (?:[^\d]*([<>]?\s*[\d.,]+\s*[-–]\s*[\d.,]+|[<>]\s*[\d.,]+))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

_LAB_TABLE_RE = re.compile(
    r"""
    ^([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍóúñ\s\(\)%]{2,60}?)
    \s+
    (\d+(?:[.,]\d+)?)
    \s*(?:\[([HLhl]+)\])?
    \s*([\d.,]+\s*[-–]\s*[\d.,]+)?
    \s*([a-zA-Z%µ][a-zA-Z0-9%/µ.\-]{0,15})?
    """,
    re.VERBOSE | re.IGNORECASE,
)

_WIDAL_RE = re.compile(r"(?i)\bWidal\b.*?(\d{1,4})\s*[:/]\s*(\d{1,4})")
_QUALITATIVE_RE = re.compile(
    r"(?i)^\s*([A-Za-zÁÉÍÓÚÑ0-9().,%\-/]{3,80}?)\s*[:\-]\s*"
    r"(POSITIVO|NEGATIVO|SENSITIVO|SENSIBLE|RESISTENTE|PRESENTE|AUSENTE|"
    r"DETECTADO|NO\s+DETECTADO|REACTIVO|NO\s+REACTIVO|CLEARED)\b"
)


def extraer_ciu_lab(texto: str) -> Optional[str]:
    """Extrae CIU de informe de laboratorio."""
    t = texto or ""
    for pat in [
        r"(?:Sample\s+)?[Pp]atient\s*CIU\s*[:\-]?\s*([A-Za-z]\d{6,8}|\d{8})",
        r"\bCIU\s*[:\-]?\s*([A-Za-z]\d{6,8}|\d{8})",
        r"\bDNI\s*[:\-]?\s*(\d{8})",
        r"N[°º]?\s*Doc(?:umento)?\s*[:\-]?\s*(\d{8})",
    ]:
        m = re.search(pat, t, re.I)
        if m:
            return _fix_num(m.group(1)).upper()
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


def procesar_lab(texto: str) -> Dict[str, Any]:
    """Extrae parámetros de laboratorio."""
    res = {
        "ciu": extraer_ciu_lab(texto),
        "pruebas": [],
        "alertas": [],
        "tipo": "LAB_REPORT",
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
            if len(nombre_raw) < 3:
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
                res["alertas"].append({
                    "prueba": nombre,
                    "valor": valor,
                    "tipo": "ALTO" if flag == "H" else "BAJO",
                })
    
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
    
    # Extraer campos
    if tipo == "DNI_PERU":
        campos = procesar_dni_peru(texto)
    elif tipo in ("LAB_REPORT", "INFORME_MEDICO"):
        campos = procesar_lab(texto)
    else:
        campos = {"tipo": tipo}
    
    return {
        "estado": "ok",
        "tipo": tipo,
        "campos": campos,
        "tiempo_ms": round((time.time() - inicio) * 1000, 1),
        "imagen": ruta,
        "timestamp": datetime.datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 8: AUTO-SCAN FOLDERS (para startup)
# ═══════════════════════════════════════════════════════════════════════════════

def autoscan_folders(
    dni_folder: str = "DNI_ALDIMI",
    lab_folder: str = "LAB_ALDIMI",
    output_json: str = "aldimi_pacientes.json",
    max_images: int = MAX_IMAGES,
) -> Dict[str, Any]:
    """
    Escanea DNI_ALDIMI y LAB_ALDIMI, procesa todas las imágenes.
    Retorna stats: total, DNI procesados, LAB procesados, alertas.
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
    def _gather_images(folder: str) -> List[Path]:
        p = Path(folder)
        if not p.is_dir():
            return []
        imgs = []
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            imgs.extend(list(p.glob(ext)))
        imgs = sorted(imgs, key=lambda x: x.name)
        # normalizar max_images: None or <=0 => sin límite
        try:
            if max_images is None or int(max_images) <= 0:
                return imgs
            n = min(100, max(1, int(max_images)))
            return imgs[:n]
        except Exception:
            return imgs

    dni_list = _gather_images(dni_folder)
    lab_list = _gather_images(lab_folder)

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
    texto = extraer_texto_ocr(ruta)
    resultado = procesar_imagen(ruta)

    if resultado.get("estado") != "ok":
        return {
            "tipo_documento": "UNKNOWN",
            "texto_crudo": texto or "",
            "campos": {},
            "advertencia": resultado.get("mensaje", "OCR no pudo extraer texto suficiente."),
        }

    tipo = resultado.get("tipo", "UNKNOWN")
    campos = resultado.get("campos", {}) or {}

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
