# -*- coding: utf-8 -*-
"""
main.py — API de ALDIMI 2.0 (FastAPI)

Junta ocr.py + chatbot.py + persistencia compartida en db.py.
Corre 100% local, sin depender de Render.

Cómo correrlo:
    pip install fastapi uvicorn python-multipart opencv-python-headless pytesseract
    uvicorn main:app --reload --port 8000

Endpoints principales:
    POST /ocr/procesar        → sube una imagen, devuelve texto + campos (SIN guardar)
    POST /pacientes/guardar   → guarda/actualiza un paciente con los campos YA corregidos
    GET  /pacientes/{ciu}     → devuelve el expediente completo de un paciente
    GET  /pacientes           → lista todos los pacientes registrados
    POST /chat                → mensaje de texto al chatbot (ver chatbot.py)
"""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ocr
from db import cargar_bd, guardar_bd
from chatbot import router as chatbot_router

# ─────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────

app = FastAPI(title="ALDIMI 2.0 API")

# CORS abierto: el frontend (index.html/chatbot.html) se sirve aparte
# (Live Server, otro puerto, etc.), así que el navegador necesita permiso
# explícito para llamar a esta API desde otro origen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas del chatbot (POST /chat) montadas sobre la misma app
app.include_router(chatbot_router)


# ─────────────────────────────────────────────────────────────
# Esquemas de entrada (Pydantic) — lo que manda el frontend
# ─────────────────────────────────────────────────────────────

class GuardarPacienteRequest(BaseModel):
    ciu: str
    tipo_documento: str          # "DNI" o "LAB"
    campos: dict                  # campos YA revisados/corregidos por el usuario


# ─────────────────────────────────────────────────────────────
# Endpoints — OCR
# ─────────────────────────────────────────────────────────────

@app.post("/ocr/procesar")
async def ocr_procesar(archivo: UploadFile = File(...)):
    """
    Recibe una imagen (DNI o informe de lab), la procesa con ocr.py
    y devuelve texto crudo + campos detectados. NO guarda nada todavía:
    el frontend debe mostrar estos campos en un formulario editable
    y recién llamar a /pacientes/guardar cuando el usuario confirme.
    """
    extensiones_validas = (".png", ".jpg", ".jpeg")
    if not archivo.filename.lower().endswith(extensiones_validas):
        raise HTTPException(400, "Formato no soportado. Usa PNG o JPG.")

    # Tesseract necesita un archivo en disco, así que guardamos temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(archivo.filename).suffix) as tmp:
        shutil.copyfileobj(archivo.file, tmp)
        ruta_temporal = tmp.name

    try:
        resultado = ocr.procesar_documento(ruta_temporal)
    except Exception as e:
        raise HTTPException(500, f"Error procesando la imagen: {e}")
    finally:
        os.remove(ruta_temporal)

    if resultado["tipo_documento"] == "UNKNOWN":
        resultado["advertencia"] = (
            "No se pudo determinar si es un DNI o un informe de laboratorio. "
            "Revisa el texto extraído y completa los campos manualmente."
        )
    return resultado


# ─────────────────────────────────────────────────────────────
# Endpoints — Pacientes / Expedientes
# ─────────────────────────────────────────────────────────────

@app.post("/pacientes/guardar")
async def guardar_paciente(req: GuardarPacienteRequest):
    """
    Guarda (o actualiza) un paciente en el JSON, usando el CIU como llave.
    - Si tipo_documento == 'DNI'  → crea/actualiza datos_personales.
    - Si tipo_documento == 'LAB'  → agrega un informe de laboratorio
      al expediente existente (no lo reemplaza, se acumula).
    """
    ciu = req.ciu.strip().upper()
    if not ciu:
        raise HTTPException(400, "El CIU no puede estar vacío.")

    bd = cargar_bd()
    registro = bd.get(ciu, {
        "ciu": ciu,
        "datos_personales": {},
        "informes_laboratorio": [],
        "alertas_clinicas": [],
        "creado_en": datetime.now().isoformat(),
    })

    if req.tipo_documento == "DNI":
        registro["datos_personales"] = req.campos

    elif req.tipo_documento == "LAB":
        informe = {
            "pruebas": req.campos.get("pruebas", []),
            "alertas_detectadas": req.campos.get("alertas_detectadas", []),
            "registrado_en": datetime.now().isoformat(),
        }
        registro.setdefault("informes_laboratorio", []).append(informe)
        registro.setdefault("alertas_clinicas", []).extend(informe["alertas_detectadas"])

    else:
        raise HTTPException(400, "tipo_documento debe ser 'DNI' o 'LAB'.")

    registro["actualizado_en"] = datetime.now().isoformat()
    bd[ciu] = registro
    guardar_bd(bd)

    return {"mensaje": "Paciente guardado correctamente.", "registro": registro}


@app.get("/pacientes/{ciu}")
async def obtener_paciente(ciu: str):
    bd = cargar_bd()
    ciu = ciu.strip().upper()
    if ciu not in bd:
        raise HTTPException(404, f"No se encontró un paciente con CIU {ciu}.")
    return bd[ciu]


@app.get("/pacientes")
async def listar_pacientes():
    bd = cargar_bd()
    return {"total": len(bd), "pacientes": list(bd.values())}


@app.get("/")
async def raiz():
    return {"estado": "ALDIMI API activa", "pacientes_registrados": len(cargar_bd())}