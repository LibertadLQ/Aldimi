# -*- coding: utf-8 -*-
"""
ocr.py — ALDIMI
================
Convierte una imagen (o texto ya extraído por OCR) en un JSON estructurado.

Flujo:
  imagen -> extraer_texto_ocr() -> clasificar_documento()
         -> [DNI_PERU|DNI_USA]  -> extraer_campos_dni()
         -> [LAB_REPORT]        -> extraer_campos_lab()

La idea clave: DNI y LAB son problemas distintos, así que NO comparten
parser. DNI busca 3-4 campos fijos por etiqueta conocida. LAB recorre
línea por línea, descarta ruido (encabezados, método, página, firmas) y
solo interpreta líneas con forma "nombre valor [unidad] [flag] [referencia]".
"""

import re
import os
from typing import Optional, Dict, Any, List


# ===========================================================================
# 0. OCR CRUDO
# ===========================================================================

def extraer_texto_ocr(ruta_imagen: str, lang: str = "spa+eng") -> str:
    """Ejecuta Tesseract sobre la imagen y devuelve el texto crudo."""
    import pytesseract
    from PIL import Image

    # Ruta directa al ejecutable de Tesseract en Windows. Si lo instalaste
    # en otra carpeta, ajusta esta línea con tu ruta real.
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    img = Image.open(ruta_imagen)
    texto = pytesseract.image_to_string(img, lang=lang, config="--psm 6 --oem 3")
    return (texto or "").strip()


# ===========================================================================
# 1. CLASIFICACIÓN DEL DOCUMENTO
# ===========================================================================

_LAB_KW = [
    "hemoglobin", "hemograma", "hematocrito", "leucocit", "glucosa",
    "laboratorio", "diagnostic", "patient ciu", "resultado actual",
    "valor referencial", "reference range", "bio. ref", "specimen",
    "test name", "método", "muestra", "cliente", "fecha de admisión",
    "fecha de muestra", "número de guía", "n° de guía", "n de guia",
    "entidad prestadora", "cmp:", "rne:", "resultados", "examenes realizados",
]
_PERU_KW = [
    "república del perú", "documento nacional de identidad", "reniec",
    "primer apellido", "prenombres", "fecha de caducidad", "cui",
]
_USA_KW = [
    "west virginia", "driver license", "dl no", "governor", "4d dl", "dob",
]


def clasificar_documento(texto: str) -> str:
    """Devuelve 'DNI_PERU' | 'DNI_USA' | 'LAB_REPORT' | 'UNKNOWN'.

    Clasificación por conteo de palabras clave: cada categoría "vota" y
    gana la de mayor puntaje. Si nadie vota, es UNKNOWN.
    """
    t = (texto or "").lower()

    lab_s = sum(1 for k in _LAB_KW if k in t)
    peru_s = sum(1 for k in _PERU_KW if k in t)
    usa_s = sum(1 for k in _USA_KW if k in t)

    if lab_s == peru_s == usa_s == 0:
        return "UNKNOWN"

    max_s = max(lab_s, peru_s, usa_s)
    if max_s == lab_s and lab_s > 0:
        return "LAB_REPORT"
    if max_s == peru_s and peru_s > 0:
        return "DNI_PERU"
    return "DNI_USA"


# ===========================================================================
# 2A. EXTRACCIÓN — DNI (Perú / USA)
# ===========================================================================

def _fix_num(s: str) -> str:
    """Corrige confusiones típicas de OCR en dígitos (O→0, I→1, S→5...)."""
    return s.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "Z": "2", "B": "8"}))


def extraer_ciu_dni(texto: str, tipo_dni: str) -> Optional[str]:
    """Número de documento / licencia. Prioridad: CUI Perú > ID alfanumérico USA > 8 dígitos Perú."""
    t = texto or ""

    m = re.search(r"(?:4d\s+)?DL\s*NO\.?\s*([A-Z]{1,2}\d{5,7})\b", t, re.I)
    if m:
        return m.group(1).strip().upper()

    m = re.search(r"\bCUI\s+(\d{8})(?:-\d)?\b", t, re.I)
    if m:
        return _fix_num(m.group(1))

    # Alfanumérico USA: 1-2 letras + 5-7 dígitos (ej. W839927, WV632919)
    for m in re.finditer(r"\b([A-Z]{1,2}\d{5,7})\b(?!\d)", t):
        return m.group(1).upper()

    # 8 dígitos Perú, descartando años y números de tarjeta.
    # El OCR a veces mete un espacio suelto en medio del número
    # (ej. "43451826" -> "48451 826"), así que buscamos también en
    # una versión sin espacios entre dígitos, sin tocar el texto original.
    t_sin_espacios = re.sub(r"(?<=\d)\s+(?=\d)", "", t)
    for c in re.findall(r"\b(\d{8})\b", t) + re.findall(r"\b(\d{8})\b", t_sin_espacios):
        y4 = int(c[:4])
        if 2000 <= y4 <= 2030 or 1900 <= y4 <= 1930:
            continue
        if c.startswith("0"):
            continue
        return _fix_num(c)

    return None


_EXCL_DOC_PERU = {
    "PERU", "REPUBLICA", "NACIONAL", "DOCUMENTO", "IDENTIDAD", "REGISTRO",
    "ESTADO", "CIVIL", "CASADO", "SOLTERO", "SOLTERA", "DIVORCIADO",
    "CADUCIDAD", "CADUCA", "TARJETA", "EMISION", "NACIMIENTO", "SEXO",
    "MASCULINO", "FEMENINO", "PRIMER", "SEGUNDO", "APELLIDO", "APELLIDOS",
    "PRENOMBRES", "PRENOMBRE", "FECHA", "UBIGEO", "VOTACION", "GRUPO",
    "DONACION", "ORGANOS", "MUESTRA", "VALOR", "IDENTIFICACION",
}


def _bloque_limpio(texto: str, etiqueta_regex: str, lineas_extra: int = 2) -> Optional[str]:
    """Busca `etiqueta_regex` línea por línea y devuelve el primer bloque de
    letras "reales" (>=3 caracteres, sin contar palabras del propio documento)
    que aparezca en esa línea o en las siguientes `lineas_extra`.

    Esto evita quedarnos con basura OCR de 1-2 caracteres (ej. "S | N a")
    que a veces aparece pegada justo después de la etiqueta.
    """
    lineas = texto.split("\n")
    for i, line in enumerate(lineas):
        if re.search(etiqueta_regex, line, re.I):
            for j in range(i + 1, min(i + 1 + lineas_extra, len(lineas))):
                tokens = [
                    w for w in re.findall(r"[A-ZÁÉÍÓÚÑa-záéíóúñ]{3,}", lineas[j])
                    if w.upper() not in _EXCL_DOC_PERU
                ]
                if tokens:
                    return " ".join(tokens[:3])
    return None


def extraer_nombre_apellido_dni(texto: str, tipo_dni: str):
    """DNI_PERU: etiquetas 'Primer/Segundo Apellido' + 'Prenombres'.
    DNI_USA : campos numerados '1 APELLIDO' / '2 NOMBRE'.
    """
    t = texto
    nombres = apellidos = None

    if tipo_dni == "DNI_PERU":
        ap1 = _bloque_limpio(t, r"primer\s*apellido")
        ap2 = _bloque_limpio(t, r"segundo\s*apellido")
        prenom = _bloque_limpio(t, r"prenombres?", lineas_extra=1)

        if ap1:
            apellidos = (ap1 + (" " + ap2 if ap2 else "")).strip()
        if prenom:
            nombres = prenom

    elif tipo_dni == "DNI_USA":
        for line in t.split("\n"):
            line = line.strip()
            m = re.match(r"^1\s+([A-Z][A-Z\s]{1,30})", line)
            if m and not apellidos:
                apellidos = m.group(1).strip()
            m = re.match(r"^2\s+([A-Z][A-Z\s]{1,30})", line)
            if m and not nombres:
                nombres = m.group(1).strip()

    return nombres, apellidos


def extraer_fecha_nacimiento_dni(texto: str, tipo_dni: str) -> Optional[str]:
    """Devuelve fecha como MM/DD/YYYY, validando año 1930-2015."""
    t = texto
    YEAR_MIN, YEAR_MAX = 1930, 2015

    if tipo_dni == "DNI_PERU":
        m = re.search(r"Fecha\s+de\s+Nacimiento[:\s]+(\d{1,2})\s+(\d{1,2})\s+(\d{4})", t, re.I)
        if m:
            dd, mm, yyyy = m.groups()
            if YEAR_MIN <= int(yyyy) <= YEAR_MAX:
                return f"{mm.zfill(2)}/{dd.zfill(2)}/{yyyy}"

        m = re.search(r"\b(\d{2})\s+(\d{2})\s+(\d{4})\b", t)
        if m:
            dd, mm, yyyy = m.groups()
            if YEAR_MIN <= int(yyyy) <= YEAR_MAX:
                return f"{mm}/{dd}/{yyyy}"

    elif tipo_dni == "DNI_USA":
        for pat in [r"3\s+DOB\s+(\d{2}/\d{2}/\d{4})", r"DOB\s+(\d{2}/\d{2}/\d{4})"]:
            m = re.search(pat, t, re.I)
            if m:
                yyyy = int(m.group(1).split("/")[2])
                if YEAR_MIN <= yyyy <= YEAR_MAX:
                    return m.group(1)

        for m in re.finditer(r"\b(\d{2})/(\d{2})/(\d{4})\b", t):
            if YEAR_MIN <= int(m.group(3)) <= YEAR_MAX:
                return m.group(0)

    return None


def extraer_campos_dni(texto: str, tipo_dni: str) -> Dict[str, Any]:
    """Punto de entrada para documentos de identidad."""
    ciu = extraer_ciu_dni(texto, tipo_dni)
    nombres, apellidos = extraer_nombre_apellido_dni(texto, tipo_dni)
    fecha_nacimiento = extraer_fecha_nacimiento_dni(texto, tipo_dni)

    return {
        "ciu": ciu,
        "nombres": nombres or "NO_DETECTADO",
        "apellidos": apellidos or "NO_DETECTADO",
        "fecha_nacimiento": fecha_nacimiento or "NO_DETECTADO",
    }


# ===========================================================================
# 2B. EXTRACCIÓN — INFORME DE LABORATORIO
# ===========================================================================

# Líneas a IGNORAR (ruido de cabecera/pie, no son pruebas)
_SKIP_RE = re.compile(
    r"^(reference|rango\s*normal|método|method|specimen|equipment|"
    r"sample\s*no|collection|report\s*date|report\s*release|printed|"
    r"note\s*:|page\s*\d|p[aá]gina|nabl|accuracy|"
    r"test\s*name?|result|unit|ref\.?\s*range|bio\.?\s*ref|biological\s*ref|"
    r"description|investigation|analisis|observed|sensitivity|antibiotic|"
    r"sr\.?\s*no|end\s*of\s*report|not\s*valid|"
    r"home\s*collection|clinic\s*correlat|these\s*are\s*only|"
    r"methodology|equipment\s*:|facility\s*:|"
    r"ordering\s*doctor|episode\s*no|ref\.\s*doctor|patient\s*type|"
    r"m[eé]dico|paciente|historia|documento|nacional\s*de|identidad|"
    r"sexo|edad|cliente|direcci[oó]n|localidad|entidad|registro|plan|"
    r"n[uú]mero\s*de\s*gu[ií]a|cmp|rne|servicio|admisi[oó]n)",
    re.IGNORECASE,
)

# Fila con ":" explícito → "Nombre: valor unidad [FLAG] referencia"
# Separador limitado a ":" (NO "-") para no confundir con un rango de
# referencia tipo "123-103" que aparece más adelante en la misma línea.
_LAB_NUM = re.compile(
    r"""
    ^([\wÁÉÍÓÚÑáéíóúñ()\[\]{}#\./,+%°\s]{3,85}?)      # G1 nombre
    \s*:\s*
    (\d+(?:[.,]\d+)?)                                  # G2 valor
    \s*
    ([a-zA-ZµμΩ%°][a-zA-Z0-9µμ%/^.·\-]{0,20})?          # G3 unidad
    \s*(?:\[([HLhl]+)\])?                               # G4 flag
    (?:[^\d\-]*?([<>]?\s*[\d.,]+\s*[-–]\s*[\d.,]+|[<>]\s*[\d.,]+))?  # G5 referencia
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Fila tipo tabla, SIN ":" → "NOMBRE  valor  referencia  unidad"
# (formato típico de reportes peruanos: "Hemoglobina 146 123-103 g/dl")
_LAB_TABLE = re.compile(
    r"""
    ^([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ\s\(\)%]{2,60}?)   # G1 nombre
    \s+
    (\d+(?:[.,]\d+)?)                                            # G2 valor
    \s*(?:\[([HLhl]+)\])?                                        # G3 flag
    \s*([\d.,]+\s*[-–]\s*[\d.,]+|[<>]\s*[\d.,]+)?                # G4 referencia
    \s*([a-zA-Z%µ][a-zA-Z0-9%/µ\.\^\-]{0,15})?                   # G5 unidad
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Nombres OCR-rotos -> nombre clínico canónico (bilingüe ES/EN)
_NAME_MAP_LAB = [
    (r"c.?reactive\s*protein|^crp\b", "Proteína C Reactiva (CRP)"),
    (r"h(a?e)?mo?glo?[bh]in[ae]?|^hb\b|hem[oa]glob", "Hemoglobina (Hb)"),
    (r"h(a?e)?ma?to?cri?to?|haematocrit|hematocrit|^pcv\b", "Hematocrito (PCV)"),
    (r"(total\s+)?rbc|hemat[ií]es|red\s*blood\s*cell", "Glóbulos Rojos (RBC)"),
    (r"(total\s+)?(wbc|leucocit|leukocyt|white\s*blood)", "Leucocitos (WBC)"),
    (r"platelet|plaquetas", "Plaquetas"),
    (r"neutr[oó]filos?\s*segment|neutrophil", "Neutrófilos Segmentados"),
    (r"linfo?cit|lymphocyt", "Linfocitos"),
    (r"eosin[oó]filos?|eosinophil", "Eosinófilos"),
    (r"mono?cit|monocyt", "Monocitos"),
    (r"bas[oó]filos?|basophil", "Basófilos"),
    (r"volumen\s*corpuscular\s*me[dt]io|\bmcv\b", "VCM (MCV)"),
    (r"hemoglobin[ae]\s*corpuscular\s*media|\bmch\b", "HCM (MCH)"),
    (r"concentraci[oó]n.*hemoglob.*corpuscular|\bmchc\b", "CHCM (MCHC)"),
    (r"(indice|índice)\s*de\s*anisocitosis|\brdw\b", "Ancho Distribución Eritrocitos (RDW)"),
    (r"bastones?|band\s*cells?", "Bastones"),
    (r"glucosa|glucose", "Glucosa"),
]


def _skip_lab(nombre: str) -> bool:
    return bool(_SKIP_RE.match(nombre.strip()))


def _norm_nombre_lab(raw: str) -> str:
    low = raw.lower()
    for pat, canon in _NAME_MAP_LAB:
        if re.search(pat, low, re.I):
            return canon
    return re.sub(r"\s+", " ", raw).strip().title()


def _infer_flag_lab(valor: float, ref_raw: Optional[str]) -> Optional[str]:
    """Si el OCR no trajo [H]/[L] explícito, lo infiere comparando contra el rango."""
    if not ref_raw:
        return None
    m = re.search(r"([\d.,]+)\s*[-–]\s*([\d.,]+)", ref_raw)
    if not m:
        return None
    try:
        lo, hi = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    except ValueError:
        return None
    if valor < lo:
        return "L"
    if valor > hi:
        return "H"
    return None


def extraer_ciu_lab(texto: str) -> Optional[str]:
    """CIU / N° historia dentro de un informe de laboratorio."""
    t = texto or ""
    for pat in [
        r"(?:Sample\s+)?[Pp]atient\s*CIU\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
        r"\bCIU\s*[:\-]?\s*([A-Za-z]\d{5,8}|\d{8})",
        r"N[°º]?\s*Doc(?:umento)?\s*\.?\s*[:\-]?\s*(\d{8})",
        r"Historia\s*[:\-]?\s*(\d{5,10})",
    ]:
        m = re.search(pat, t, re.I)
        if m:
            return _fix_num(m.group(1)).upper()
    return None


def extraer_campos_lab(texto: str) -> Dict[str, Any]:
    """Punto de entrada para informes de laboratorio.

    A diferencia del DNI (campos fijos), aquí recorremos línea por línea:
      1. Si la línea matchea ruido conocido (_SKIP_RE) -> se descarta.
      2. Si matchea el patrón numérico o de tabla -> se registra como prueba.
      3. Se normaliza el nombre y se infiere el flag H/L si falta.
    """
    res: Dict[str, Any] = {"ciu": extraer_ciu_lab(texto), "pruebas": [], "alertas_detectadas": []}
    seen = set()

    for linea in (texto or "").split("\n"):
        ls = linea.strip()
        if len(ls) < 4:
            continue
        if _skip_lab(ls):
            continue

        m_num = _LAB_NUM.search(ls)
        m_tab = None if m_num else _LAB_TABLE.search(ls)
        m = m_num or m_tab
        if not m:
            continue

        nombre_raw = m.group(1).strip().rstrip(" :-")
        if _skip_lab(nombre_raw) or len(nombre_raw) < 3:
            continue
        # descarta filas cuyo "nombre" es en realidad solo un número (paginación, etc.)
        if re.match(r"^\s*\d{1,3}\.?\s*$", nombre_raw):
            continue

        nombre = _norm_nombre_lab(nombre_raw)
        key = nombre.lower()
        if key in seen:
            continue

        valor_raw = m.group(2).strip()
        try:
            valor = float(valor_raw.replace(",", "."))
        except ValueError:
            continue  # si no es un número real, no es una prueba de lab válida

        if m_num:
            unidad = (m.group(3) or "").strip() or None
            flag = (m.group(4) or "").upper() or None
            referencia = (m.group(5) or "").strip() or None
        else:  # _LAB_TABLE: orden distinto de grupos (flag antes que referencia)
            flag = (m.group(3) or "").upper() or None
            referencia = (m.group(4) or "").strip() or None
            unidad = (m.group(5) or "").strip() or None

        if not flag:
            flag = _infer_flag_lab(valor, referencia)

        seen.add(key)
        prueba = {
            "nombre": nombre,
            "valor": round(valor, 4),
            "unidad": unidad or "",
            "referencia": referencia or "",
            "flag": flag or "",
        }
        res["pruebas"].append(prueba)

        if flag in ("H", "L"):
            res["alertas_detectadas"].append({
                "prueba": nombre,
                "valor": valor,
                "tipo": "ALTO [H]" if flag == "H" else "BAJO [L]",
                "unidad": unidad or "",
                "referencia": referencia or "",
            })

    return res


# ===========================================================================
# 3. ORQUESTADOR — punto de entrada único para main.py / FastAPI
# ===========================================================================

def procesar_texto(texto: str) -> Dict[str, Any]:
    """Recibe texto OCR crudo y devuelve el JSON estructurado final."""
    tipo = clasificar_documento(texto)

    if tipo in ("DNI_PERU", "DNI_USA"):
        campos = extraer_campos_dni(texto, tipo)
    elif tipo == "LAB_REPORT":
        campos = extraer_campos_lab(texto)
    else:
        campos = {}

    return {
        "tipo_documento": tipo,
        "texto_crudo": texto,
        "campos": campos,
    }


def procesar_documento(ruta_imagen: str) -> Dict[str, Any]:
    """Punto de entrada de más alto nivel: recibe una ruta de imagen en disco."""
    texto = extraer_texto_ocr(ruta_imagen)
    return procesar_texto(texto)