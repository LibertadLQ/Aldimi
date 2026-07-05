# -*- coding: utf-8 -*-
"""
main.py — API local de ALDIMI

Proporciona endpoints para:
- POST /ocr/procesar — Procesa una imagen y extrae datos
- GET /pacientes/{ciu} — Obtiene expediente de un paciente
- GET /pacientes — Lista todos los pacientes
"""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import ocr_robusto as ocr
except ImportError:
    import ocr

from db import cargar_bd, guardar_bd
from expediente import persistir_ocr_resultado, sincronizar_carpetas

app = FastAPI(title="ALDIMI 2.0 Local API")

# CORS para que chatbot.html pueda llamar desde localhost:5500
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup: escanear carpetas locales
@app.on_event("startup")
async def startup_scan():
    """Al iniciar, escanea DNI_ALDIMI y LAB_ALDIMI."""
    print("[STARTUP] Iniciando escaneo automático de carpetas...")
    try:
        max_images_env = os.environ.get("ALDIMI_MAX_IMAGES", "0")
        try:
            max_images = int(max_images_env)
        except Exception:
            max_images = 0

        resultados = sincronizar_carpetas(max_images=max_images)
        
        print(f"[STARTUP] ✅ Escaneo completado:")
        print(f"         Imágenes procesadas: {resultados['procesados']}")
        
    except Exception as e:
        print(f"[STARTUP] ⚠️ Error durante escaneo: {e}")


# Esquemas
class GuardarPacienteRequest(BaseModel):
    ciu: str
    tipo_documento: str  # "DNI" o "LAB"
    campos: dict


# Endpoints
@app.post("/ocr/procesar")
async def ocr_procesar(archivo: UploadFile = File(...)):
    """Procesa una imagen (DNI o informe) y extrae datos."""
    extensiones_validas = (".png", ".jpg", ".jpeg")
    if not archivo.filename.lower().endswith(extensiones_validas):
        raise HTTPException(400, "Formato no soportado. Usa PNG o JPG.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(archivo.filename).suffix) as tmp:
        shutil.copyfileobj(archivo.file, tmp)
        ruta_temporal = tmp.name

    try:
        resultado = ocr.procesar_documento(ruta_temporal)
        persistir_ocr_resultado(ruta_temporal, resultado, fuente="upload")
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


@app.post("/pacientes/guardar")
async def guardar_paciente(req: GuardarPacienteRequest):
    """Guarda o actualiza un paciente."""
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
    """Obtiene expediente de un paciente."""
    bd = cargar_bd()
    ciu = ciu.strip().upper()
    if ciu not in bd:
        raise HTTPException(404, f"No se encontró un paciente con CIU {ciu}.")
    return bd[ciu]


@app.get("/pacientes")
async def listar_pacientes():
    """Lista todos los pacientes."""
    bd = cargar_bd()
    return {"total": len(bd), "pacientes": list(bd.values())}


@app.get("/")
async def raiz():
    """Estado de la API."""
    return {"estado": "ALDIMI API activa", "pacientes_registrados": len(cargar_bd())}
