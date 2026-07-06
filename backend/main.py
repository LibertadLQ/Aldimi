# -*- coding: utf-8 -*-
"""
main.py — API FastAPI para ALDIMI

Combina:
- el endpoint de chat del módulo chatbot,
- el procesamiento OCR y guardado de pacientes,
- y el escaneo automático de carpetas locales al iniciar.
"""

import os
import shutil
import tempfile
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.chatbot import procesar_mensaje
from backend.db import cargar_bd, guardar_bd
from backend.expediente import persistir_ocr_resultado, sincronizar_carpetas
from backend.storage import OCR_IMAGES_DIR

try:
    from backend.ocr_robusto import procesar_documento as procesar_documento_ocr
except ImportError:
    from backend.ocr import procesar_documento as procesar_documento_ocr


app = FastAPI(
    title="ALDIMI API",
    description="API backend para el frontend estático de ALDIMI.",
    version="1.0.0",
)

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


@app.on_event("startup")
async def startup_scan() -> None:
    """Al iniciar, escanea DNI_ALDIMI y LAB_ALDIMI.

    Comportamiento controlado por env `ALDIMI_WAIT_FOR_SCAN`:
    - si está a '1' o 'true' (por defecto), el escaneo se ejecuta de forma
      sincrónica y bloqueante antes de que la API acepte peticiones.
    - si está a '0' o 'false', el escaneo se programa en background (no bloqueante).
    """
    wait_env = os.environ.get("ALDIMI_WAIT_FOR_SCAN", "1").lower()
    wait_for_scan = wait_env in ("1", "true", "yes")

    max_images_dni_env = os.environ.get("ALDIMI_SCAN_DNI", "1")
    max_images_lab_env = os.environ.get("ALDIMI_SCAN_LAB", "1")
    try:
        max_images_dni = int(max_images_dni_env)
    except Exception:
        max_images_dni = 1
    try:
        max_images_lab = int(max_images_lab_env)
    except Exception:
        max_images_lab = 1

    print(f"[STARTUP] ALDIMI_WAIT_FOR_SCAN={wait_env}, ALDIMI_SCAN_DNI={max_images_dni}, ALDIMI_SCAN_LAB={max_images_lab}")

    if wait_for_scan:
        print("[STARTUP] Ejecutando escaneo automático de carpetas (modo bloqueante)...")
        try:
            resultados = sincronizar_carpetas(max_images_dni=max_images_dni, max_images_lab=max_images_lab)
            print("[STARTUP] Escaneo completado.")
            print(f"         Imagenes procesadas: {resultados.get('procesados')}")
        except Exception as exc:
            print(f"[STARTUP] Error durante escaneo bloqueante: {exc}")
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

            asyncio.create_task(_run_sync_scan())
        except Exception as exc:
            print(f"[STARTUP] Error al programar escaneo: {exc}")


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
    bd = cargar_bd()
    return {"total": len(bd) if isinstance(bd, dict) else 0, "pacientes": list(bd.values()) if isinstance(bd, dict) else []}


@app.get("/pacientes/{ciu}")
def obtener_paciente(ciu: str) -> Dict[str, Any]:
    bd = cargar_bd()
    ciu = ciu.strip().upper()
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
        registro["datos_personales"] = {
            "ciu": ciu,
            "tipo_documento": tipo_documento,
            "nombres": campos.get("nombres", "NO_DETECTADO"),
            "apellidos": campos.get("apellidos", "NO_DETECTADO"),
            "fecha_nacimiento": campos.get("fecha_nacimiento", "NO_DETECTADO"),
        }
    elif tipo_documento == "LAB":
        informe = {
            "fecha_carga": datetime.now().isoformat(),
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
    print("[ALDIMI] Iniciando escaneo local de carpetas...")
    print("[ALDIMI] Carpeta DNI_ALDIMI:", Path("DNI_ALDIMI").resolve())
    print("[ALDIMI] Carpeta LAB_ALDIMI:", Path("LAB_ALDIMI").resolve())

    resultados = sincronizar_carpetas(max_images_dni=max_images, max_images_lab=max_images)

    print("[ALDIMI] Escaneo local finalizado.")
    print(f"         Imágenes procesadas: {resultados['procesados']}")
    print(f"         Detalles registrados: {len(resultados['resultados'])}")
    return resultados


def main() -> None:
    max_images_env = os.environ.get("ALDIMI_MAX_IMAGES", "1")
    try:
        max_images = int(max_images_env)
    except Exception:
        max_images = 1

    ejecutar_local(max_images=max_images)


if __name__ == "__main__":
    main()
