# -*- coding: utf-8 -*-
"""Sincronización de expediente con OCR y persistencia en ALDIMI_DB."""

import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import ocr_robusto as ocr
from .config import get_scan_limit
from .db import cargar_bd, cargar_sesiones, guardar_bd, guardar_sesiones
from .storage import DNI_DIR, LAB_DIR, OCR_IMAGES_DIR

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def _listar_imagenes(carpeta: Path, max_images: int = 0) -> List[Path]:
    if not carpeta.exists():
        return []
    images = [p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    images.sort(key=lambda p: p.name.lower())
    if max_images and max_images > 0:
        return images[:max_images]
    return images


def _copiar_imagen_a_db(ruta_origen: str) -> Optional[Path]:
    origen = Path(ruta_origen)
    if not origen.exists():
        return None
    OCR_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = f"{timestamp}_{origen.stem[:40]}{origen.suffix.lower()}"
    destino = OCR_IMAGES_DIR / nombre
    shutil.copy2(origen, destino)
    return destino


def _crear_registro_paciente(ciu: str) -> Dict[str, Any]:
    return {
        "ciu": ciu,
        "datos_personales": {},
        "informes_laboratorio": [],
        "alertas_clinicas": [],
        "documentos_ocr": [],
        "creado_en": datetime.now().isoformat(),
    }


def _normalizar_ciu(ciu: str) -> str:
    if not ciu:
        return ""
    ciu = str(ciu).strip().upper()
    if re.fullmatch(r"[A-Z]{1,2}\d{5,7}", ciu):
        return re.sub(r"[A-Z]", "", ciu)
    return ciu


def _normalizar_campos_dni(campos: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    campos = campos or {}
    def clean(v: Any) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if s.upper() == "NO_DETECTADO":
            return ""
        return s

    return {
        "ciu": _normalizar_ciu(clean(campos.get("ciu", ""))) or "",
        "nombres": clean(campos.get("nombres", "")),
        "apellidos": clean(campos.get("apellidos", "")),
        "fecha_nacimiento": clean(campos.get("fecha_nacimiento", "")),
    }


def persistir_ocr_resultado(ruta_imagen: str, resultado: Dict[str, Any], fuente: str = "upload") -> Dict[str, Any]:
    """Guarda un resultado OCR en ALDIMI_DB como sesión y actualiza el expediente si es posible."""
    timestamp = datetime.now().isoformat()
    copia = None
    if fuente == "upload":
        copia = _copiar_imagen_a_db(ruta_imagen)

    tipo_documento = resultado.get("tipo_documento", "UNKNOWN")
    campos = resultado.get("campos", {}) or {}
    if tipo_documento in {"LAB_REPORT", "INFORME_MEDICO"}:
        try:
            if not campos.get("pruebas") or not campos.get("alertas_detectadas"):
                hallazgos = ocr.extraer_alertas_de_texto(resultado.get("texto_crudo", ""))
                if hallazgos.get("pruebas"):
                    campos["pruebas"] = hallazgos["pruebas"]
                if hallazgos.get("alertas_detectadas"):
                    campos["alertas_detectadas"] = hallazgos["alertas_detectadas"]
                    campos.setdefault("alertas", hallazgos["alertas_detectadas"])
                    print(f"[PERSIST] Fallback alertas robustas aplicadas: {len(hallazgos['alertas_detectadas'])} alertas")
        except Exception as exc:
            print(f"[PERSIST] Fallback alertas robustas falló: {exc}")

    ciu_raw = str(campos.get("ciu", "")).strip().upper() if isinstance(campos, dict) else ""
    ciu = _normalizar_ciu(ciu_raw) if ciu_raw and ciu_raw != "NO_DETECTADO" else ""
    key = ciu or ciu_raw

    origen_path = Path(ruta_imagen)
    archivo_origen = str(origen_path.resolve()) if origen_path.exists() else ruta_imagen

    documento = {
        "id": f"ocr_{timestamp}",
        "timestamp": timestamp,
        "fuente": fuente,
        "archivo_origen": archivo_origen,
        "archivo_copia": str(copia.resolve()) if copia else None,
        "tipo_documento": tipo_documento,
        "texto_crudo": resultado.get("texto_crudo", ""),
        "campos": campos,
        "advertencia": resultado.get("advertencia"),
    }

    sesiones = cargar_sesiones()
    existing_sesion = next(
        (s for s in sesiones if s.get("archivo_origen") == archivo_origen and s.get("fuente") == fuente),
        None,
    )
    if existing_sesion:
        existing_sesion.update(documento)
    else:
        sesiones.append(documento)
    guardar_sesiones(sesiones)

    if key:
        bd = cargar_bd()
        registro = None
        registro_clave = None

        if ciu and ciu in bd:
            registro = bd[ciu]
            registro_clave = ciu
        elif ciu_raw and ciu_raw in bd:
            registro = bd[ciu_raw]
            registro_clave = ciu_raw
        else:
            registro = _crear_registro_paciente(key)
            registro_clave = key

        if ciu and ciu_raw and ciu != ciu_raw and ciu_raw in bd and registro_clave != ciu:
            registro = bd.pop(ciu_raw)
            registro_clave = ciu
            registro["ciu"] = ciu

        documentos = registro.setdefault("documentos_ocr", [])
        existing_doc = next(
            (d for d in documentos if d.get("archivo_origen") == archivo_origen and d.get("fuente") == fuente),
            None,
        )

        if existing_doc:
            existing_doc.update(documento)
        else:
            documentos.append(documento)

        registro["actualizado_en"] = timestamp
        if tipo_documento in {"DNI_PERU", "DNI_USA"}:
            registro["datos_personales"] = {
                **registro.get("datos_personales", {}),
                **_normalizar_campos_dni(campos),
            }
        elif tipo_documento == "LAB_REPORT" and existing_doc is None:
            informe = {
                "pruebas": campos.get("pruebas", []),
                "alertas_detectadas": campos.get("alertas_detectadas", []),
                "registrado_en": timestamp,
            }
            print(f"[PERSIST] LAB_REPORT: guardando {len(informe['pruebas'])} pruebas, {len(informe['alertas_detectadas'])} alertas")
            registro.setdefault("informes_laboratorio", []).append(informe)
            registro.setdefault("alertas_clinicas", []).extend(informe["alertas_detectadas"])

        bd[registro_clave] = registro
        guardar_bd(bd)

    return {"documento": documento, "paciente_actualizado": bool(ciu)}


def sincronizar_carpetas(max_images_dni: int = 0, max_images_lab: int = 0) -> Dict[str, Any]:
    """Procesa imágenes de DNI_ALDIMI y LAB_ALDIMI y las guarda en ALDIMI_DB.

    Si no se pasa límite positivo, no procesa nada por defecto para evitar cargar carpetas completas.
    """
    # Usar el límite configurado en backend/config.py (SCAN_LIMIT = 1-100)
    limit = get_scan_limit()
    max_images_dni = limit
    max_images_lab = limit
    print(f"[SYNC] Límite de escaneo: {limit} archivo(s)")

    resultados = []

    dni_images = _listar_imagenes(DNI_DIR, max_images=max_images_dni)
    lab_images = _listar_imagenes(LAB_DIR, max_images=max_images_lab)
    total = max(len(dni_images), len(lab_images))

    for index in range(total):
        if index < len(dni_images):
            path = dni_images[index]
            nombre_carpeta = "DNI_ALDIMI"
            print(f"[SYNC] Procesando {nombre_carpeta}: {path.name}")
            resultado = ocr.leer_documento(str(path), max_retries=3)
            print(f"[SYNC] Resultado preliminar: tipo={resultado.get('tipo_documento')} campos_keys={list((resultado.get('campos') or {}).keys())}")
            guardado = persistir_ocr_resultado(str(path), resultado, fuente=nombre_carpeta)
            print(f"[SYNC] Persistencia: paciente_actualizado={guardado.get('paciente_actualizado')}")
            resultados.append({
                "carpeta": nombre_carpeta,
                "archivo": path.name,
                "tipo_documento": resultado.get("tipo_documento"),
                "ciu": (resultado.get("campos", {}) or {}).get("ciu"),
                "guardado": guardado,
            })

        if index < len(lab_images):
            path = lab_images[index]
            nombre_carpeta = "LAB_ALDIMI"
            print(f"[SYNC] Procesando {nombre_carpeta}: {path.name}")
            resultado = ocr.leer_documento(str(path), max_retries=3)
            print(f"[SYNC] Resultado preliminar: tipo={resultado.get('tipo_documento')} campos_keys={list((resultado.get('campos') or {}).keys())}")
            guardado = persistir_ocr_resultado(str(path), resultado, fuente=nombre_carpeta)
            print(f"[SYNC] Persistencia: paciente_actualizado={guardado.get('paciente_actualizado')}")
            resultados.append({
                "carpeta": nombre_carpeta,
                "archivo": path.name,
                "tipo_documento": resultado.get("tipo_documento"),
                "ciu": (resultado.get("campos", {}) or {}).get("ciu"),
                "guardado": guardado,
            })

    return {"procesados": len(resultados), "resultados": resultados}


def _buscar_clave_registro_por_ciu(bd: Dict[str, Any], ciu_raw: str) -> Optional[str]:
    if not ciu_raw:
        return None
    ciu_raw = str(ciu_raw).strip().upper()
    ciu_norm = _normalizar_ciu(ciu_raw)

    if ciu_raw in bd:
        return ciu_raw
    if ciu_norm and ciu_norm in bd:
        return ciu_norm

    for clave in bd:
        if _normalizar_ciu(clave) == ciu_norm:
            return clave
    return None


def reparar_pacientes_desde_sesiones() -> int:
    bd = cargar_bd()
    sesiones = cargar_sesiones()
    if not sesiones:
        return 0

    cambios = 0
    for sesion in reversed(sesiones):
        if sesion.get("tipo_documento") not in {"DNI_PERU", "DNI_USA"}:
            continue

        campos = sesion.get("campos", {}) or {}
        ciu_raw = str(campos.get("ciu", "")).strip().upper()
        if not ciu_raw or ciu_raw == "NO_DETECTADO":
            continue

        registro_clave = _buscar_clave_registro_por_ciu(bd, ciu_raw)
        if registro_clave is None:
            registro_clave = _normalizar_ciu(ciu_raw) or ciu_raw
            registro = _crear_registro_paciente(registro_clave)
            bd[registro_clave] = registro
            cambios += 1
        else:
            registro = bd[registro_clave]

        datos_actuales = registro.get("datos_personales", {}) or {}
        if not datos_actuales or datos_actuales.get("nombres") in {None, "", "NO_DETECTADO"}:
            registro["datos_personales"] = _normalizar_campos_dni(campos)
            registro["datos_personales"]["ciu"] = _normalizar_ciu(ciu_raw) or ciu_raw
            registro["actualizado_en"] = sesion.get("timestamp") or datetime.now().isoformat()
            bd[registro_clave] = registro
            cambios += 1

    if cambios:
        guardar_bd(bd)
    return cambios
