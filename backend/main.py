import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
 
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
 
import ocr
from chatbot import procesar_mensaje
from db import cargar_bd, guardar_bd
from expediente import sincronizar_carpetas
 
 
# ═══════════════════════════════════════════════════════════════════════
# 1. ESCANEO LOCAL POR LOTES 
# ═══════════════════════════════════════════════════════════════════════
 
def ejecutar_local(max_images: int = 0) -> dict:
    print("[ALDIMI] Iniciando escaneo local de carpetas...")
    print("[ALDIMI] Carpeta DNI_ALDIMI:", Path("DNI_ALDIMI").resolve())
    print("[ALDIMI] Carpeta LAB_ALDIMI:", Path("LAB_ALDIMI").resolve())
 
    resultados = sincronizar_carpetas(max_images=max_images)
 
    print("[ALDIMI] Escaneo local finalizado.")
    print(f"         Imágenes procesadas: {resultados['procesados']}")
    print(f"         Detalles registrados: {len(resultados['resultados'])}")
    return resultados
 
 
# ═══════════════════════════════════════════════════════════════════════
# 2. APP FASTAPI 
# ═══════════════════════════════════════════════════════════════════════
 
app = FastAPI(title="ALDIMI Backend", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "null", 
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
 
@app.get("/")
def raiz() -> Dict[str, str]:
    return {"status": "ok", "servicio": "ALDIMI Backend"}

class ChatRequest(BaseModel):
    mensaje: str
    ciu: Optional[str] = None
 
 
@app.post("/chat")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    return procesar_mensaje(payload.mensaje, payload.ciu)
 
EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png"}
 
 
@app.post("/ocr/procesar")
async def ocr_procesar(archivo: UploadFile = File(...)) -> Dict[str, Any]:

    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in EXTENSIONES_VALIDAS:
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes JPG o PNG.")
 
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        shutil.copyfileobj(archivo.file, tmp)
        ruta_temporal = tmp.name
 
    try:
        resultado = ocr.procesar_documento(ruta_temporal)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error procesando el documento: {exc}")
    finally:
        try:
            os.remove(ruta_temporal)
        except OSError:
            pass
 
    return resultado

class GuardarPacienteRequest(BaseModel):
    ciu: str
    tipo_documento: str
    campos: Dict[str, Any]
 
 
def _crear_registro_paciente(ciu: str) -> Dict[str, Any]:
    return {
        "ciu": ciu,
        "datos_personales": {},
        "informes_laboratorio": [],
        "alertas_clinicas": [],
        "documentos_ocr": [],
        "creado_en": datetime.now().isoformat(),
    }
 
 
@app.post("/pacientes/guardar")
def pacientes_guardar(payload: GuardarPacienteRequest) -> Dict[str, Any]:

    ciu = payload.ciu.strip().upper()
    if not ciu:
        raise HTTPException(status_code=400, detail="CIU inválido.")
 
    tipo = payload.tipo_documento.upper()
    if tipo not in ("DNI", "LAB"):
        raise HTTPException(status_code=400, detail="tipo_documento debe ser 'DNI' o 'LAB'.")
 
    bd = cargar_bd()
    registro = bd.get(ciu, _crear_registro_paciente(ciu))
    timestamp = datetime.now().isoformat()
 
    if tipo == "DNI":
        registro["datos_personales"] = {
            **registro.get("datos_personales", {}),
            "nombres": payload.campos.get("nombres", "NO_DETECTADO"),
            "apellidos": payload.campos.get("apellidos", "NO_DETECTADO"),
            "fecha_nacimiento": payload.campos.get("fecha_nacimiento", "NO_DETECTADO"),
        }
    else:
        informe = {
            "pruebas": payload.campos.get("pruebas", []),
            "alertas_detectadas": payload.campos.get("alertas_detectadas", []),
            "registrado_en": timestamp,
        }
        registro.setdefault("informes_laboratorio", []).append(informe)
        registro.setdefault("alertas_clinicas", []).extend(informe["alertas_detectadas"])
 
    registro["actualizado_en"] = timestamp
    bd[ciu] = registro
    guardar_bd(bd)
 
    return {"ok": True, "ciu": ciu}

@app.get("/pacientes")
def pacientes_total() -> Dict[str, int]:
    bd = cargar_bd()
    return {"total": len(bd)}
 
@app.post("/escanear")
def escanear(max_images: int = 0) -> Dict[str, Any]:
    return ejecutar_local(max_images=max_images)
 
 
# ═══════════════════════════════════════════════════════════════════════
# 3. USO COMO SCRIPT DIRECTO
# ═══════════════════════════════════════════════════════════════════════
 
def main() -> None:
    max_images_env = os.environ.get("ALDIMI_MAX_IMAGES", "1")
    try:
        max_images = int(max_images_env)
    except Exception:
        max_images = 1
 
    ejecutar_local(max_images=max_images)
 
 
if __name__ == "__main__":
    main()
 