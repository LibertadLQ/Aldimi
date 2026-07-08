# -*- coding: utf-8 -*-
"""
main.py — API FastAPI para ALDIMI

Combina:
- el endpoint de chat del módulo chatbot,
- el procesamiento OCR y guardado de pacientes,
- y el escaneo automático de carpetas locales al iniciar.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.chatbot import procesar_mensaje
from backend.config import get_scan_limit
from backend.db import cargar_bd, guardar_bd
from backend.expediente import persistir_ocr_resultado, reparar_pacientes_desde_sesiones, sincronizar_carpetas
from backend.ocr_robusto import leer_documento as procesar_documento_ocr
from backend.storage import OCR_IMAGES_DIR


app = FastAPI(
    title="ALDIMI API",
    description="API backend para el frontend estático de ALDIMI.",
    version="1.0.0",
)

# Indica si la inicialización (escaneo + lectura de BD) ya terminó
STARTUP_READY = False
DEFAULT_SCAN_LIMIT = 1
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PacienteGuardarRequest(BaseModel):
    ciu: str
    tipo_documento: str
    campos: Dict[str, Any]


def _read_limit_env(name: str, fallback: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return fallback
    try:
        return int(str(raw).strip())
    except Exception:
        return fallback


def _is_truthy_env(name: str, fallback: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return fallback
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@app.on_event("startup")
async def startup_scan() -> None:
    """Al iniciar, solo prepara la API. El escaneo masivo queda desactivado por defecto.

    Para activar el escaneo al arrancar se debe definir:
    - ALDIMI_AUTO_SCAN=true
    - opcionalmente ALDIMI_MAX_IMAGES, ALDIMI_SCAN_DNI, ALDIMI_SCAN_LAB
    """
    global STARTUP_READY
    STARTUP_READY = False

    auto_scan = _is_truthy_env("ALDIMI_AUTO_SCAN", fallback=False)
    if not auto_scan:
        print("[STARTUP] Escaneo automático desactivado. Solo se procesarán archivos por upload o solicitud explícita.")
        try:
            cargar_bd()
            reparar_pacientes_desde_sesiones()
        except Exception as exc:
            print(f"[STARTUP] Aviso: no se pudo cargar la base de datos: {exc}")
        STARTUP_READY = True
        return

    wait_env = os.environ.get("ALDIMI_WAIT_FOR_SCAN", "0").lower()
    wait_for_scan = wait_env in ("1", "true", "yes")

    # Usar el límite configurado en backend/config.py (SCAN_LIMIT = 1-100)
    limit = get_scan_limit()
    max_images_dni = _read_limit_env("ALDIMI_SCAN_DNI", fallback=limit)
    max_images_lab = _read_limit_env("ALDIMI_SCAN_LAB", fallback=limit)
    global_top = limit

    print(f"[STARTUP] ALDIMI_AUTO_SCAN={auto_scan}, ALDIMI_WAIT_FOR_SCAN={wait_env}, ALDIMI_SCAN_DNI={max_images_dni}, ALDIMI_SCAN_LAB={max_images_lab}, ALDIMI_MAX_IMAGES={global_top}")

    if wait_for_scan:
        print("[STARTUP] Ejecutando escaneo automático de carpetas (modo bloqueante)...")
        try:
            resultados = sincronizar_carpetas(max_images_dni=max_images_dni, max_images_lab=max_images_lab)
            print("[STARTUP] Escaneo completado.")
            print(f"         Imagenes procesadas: {resultados.get('procesados')}")
        except Exception as exc:
            print(f"[STARTUP] Error durante escaneo bloqueante: {exc}")
        try:
            cargar_bd()
            reparar_pacientes_desde_sesiones()
        except Exception as exc:
            print(f"[STARTUP] Aviso: no se pudo cargar la base de datos: {exc}")
        STARTUP_READY = True
    else:
        print("[STARTUP] Programando escaneo automático de carpetas en background...")
        try:
            import asyncio

            loop = asyncio.get_running_loop()

            async def _run_sync_scan():
                try:
                    resultados = await loop.run_in_executor(
                        None,
                        sincronizar_carpetas,
                        max_images_dni,
                        max_images_lab,
                    )
                    print("[STARTUP] Escaneo completado.")
                    print(f"         Imagenes procesadas: {resultados.get('procesados')}")
                except Exception as exc:
                    print(f"[STARTUP] Error durante escaneo en background: {exc}")
                try:
                    cargar_bd()
                    reparar_pacientes_desde_sesiones()
                except Exception as exc:
                    print(f"[STARTUP] Aviso: no se pudo cargar la base de datos: {exc}")
                global STARTUP_READY
                STARTUP_READY = True

            asyncio.create_task(_run_sync_scan())
        except Exception as exc:
            print(f"[STARTUP] Error al programar escaneo: {exc}")
            STARTUP_READY = True


@app.get('/ready')
def ready() -> dict:
    """Endpoint sencillo para que el frontend consulte si el backend terminó
    la inicialización (escaneo de carpetas y lectura de BD)."""
    return {"ready": bool(STARTUP_READY)}


class ChatRequest(BaseModel):
    mensaje: str
    ciu: Optional[str] = None


@app.post("/chat")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    return procesar_mensaje(payload.mensaje, payload.ciu)


@app.get("/")
def raiz() -> Dict[str, str]:
    return {"status": "ok", "message": "ALDIMI API está disponible."}


@app.get("/pacientes")
def obtener_pacientes() -> Dict[str, Any]:
    """Retorna todos los pacientes en formato { total, pacientes }"""
    bd = cargar_bd()  # Ya extrae bd["pacientes"] automáticamente
    if isinstance(bd, dict):
        print(f"[API] GET /pacientes → {len(bd)} pacientes disponibles")
        return {"total": len(bd), "pacientes": bd}
    print(f"[API] GET /pacientes → BD inválida")
    return {"total": 0, "pacientes": {}}


def _normalizar_ciu_main(ciu: str) -> str:
    if not ciu:
        return ""
    ciu = ciu.strip().upper()
    if ciu and ciu[0].isalpha():
        digitos = "".join(ch for ch in ciu if ch.isdigit())
        return digitos or ciu
    return ciu


@app.get("/pacientes/{ciu}")
def obtener_paciente(ciu: str) -> Dict[str, Any]:
    bd = cargar_bd()
    ciu = ciu.strip().upper()
    if ciu not in bd:
        ciu_normalizado = _normalizar_ciu_main(ciu)
        if ciu_normalizado in bd:
            ciu = ciu_normalizado
        else:
            for clave in bd:
                if _normalizar_ciu_main(clave) == ciu_normalizado:
                    ciu = clave
                    break

    if ciu not in bd:
        raise HTTPException(status_code=404, detail=f"No se encontró un paciente con CIU {ciu}.")
    return bd[ciu]


@app.post("/pacientes/guardar")
async def guardar_paciente(request: PacienteGuardarRequest) -> Dict[str, Any]:
    ciu = request.ciu.strip().upper()
    if not ciu:
        raise HTTPException(status_code=400, detail="CIU inválido.")

    tipo_documento = request.tipo_documento.strip().upper()
    campos = request.campos or {}

    bd = cargar_bd()
    registro = bd.get(ciu, {})

    if tipo_documento == "DNI":
        def _clean(v):
            if v is None:
                return ""
            s = str(v).strip()
            if s.upper() == "NO_DETECTADO":
                return ""
            return s

        registro["datos_personales"] = {
            "ciu": ciu,
            "tipo_documento": tipo_documento,
            "nombres": _clean(campos.get("nombres")),
            "apellidos": _clean(campos.get("apellidos")),
            "fecha_nacimiento": _clean(campos.get("fecha_nacimiento")),
        }
    elif tipo_documento == "LAB":
        informe = {
            "fecha_carga": datetime.now().isoformat(),
            "registrado_en": datetime.now().isoformat(),
            "pruebas": campos.get("pruebas", []),
            "alertas_detectadas": campos.get("alertas_detectadas", []),
            "campos": campos,
        }
        informes = registro.get("informes_laboratorio", [])
        informes.append(informe)
        registro["informes_laboratorio"] = informes

        alertas_existentes = registro.get("alertas_clinicas", [])
        nuevas_alertas = campos.get("alertas_detectadas") or []
        registro["alertas_clinicas"] = alertas_existentes + nuevas_alertas
    else:
        raise HTTPException(status_code=400, detail="Tipo de documento desconocido.")

    bd[ciu] = registro
    guardar_bd(bd)
    return {"ok": True, "ciu": ciu}


@app.post("/ocr/procesar")
async def procesar_ocr(archivo: UploadFile = File(...)) -> Dict[str, Any]:
    if not archivo.filename:
        raise HTTPException(status_code=400, detail="No se envió ningún archivo.")

    suffix = Path(archivo.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes JPG o PNG.")

    OCR_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    nombre_temporal = f"ocr_{uuid4().hex}{suffix}"
    ruta_temporal = OCR_IMAGES_DIR / nombre_temporal

    try:
        with ruta_temporal.open("wb") as f:
            contenido = await archivo.read()
            f.write(contenido)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al guardar el archivo: {exc}")

    try:
        resultado = procesar_documento_ocr(str(ruta_temporal))
        persistir_ocr_resultado(str(ruta_temporal), resultado, fuente="upload")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al procesar el documento: {exc}")

    return resultado


def ejecutar_local(max_images: int = 0) -> dict:
    print("[ALDIMI] Escaneo local desactivado por defecto. Usa upload o activa ALDIMI_AUTO_SCAN para procesar carpetas.")
    return {"procesados": 0, "resultados": []}


def main() -> None:
    print("[ALDIMI] El modo CLI no procesa carpetas por defecto. Usa la API o activa ALDIMI_AUTO_SCAN.")


if __name__ == "__main__":
    main()
