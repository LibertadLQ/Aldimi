from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile, os

import aldimi_web as aldimi

app = FastAPI(title="ALDIMI 2.0 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class MensajeChat(BaseModel):
    mensaje: str

@app.get("/")
def raiz():
    return {"estado": "ALDIMI 2.0 API corriendo", "pacientes_en_bd": len(aldimi._BD)}

@app.get("/health")
def health():
    return {"ok": True, "pacientes_en_bd": len(aldimi._BD)}

@app.post("/chat")
def chat(body: MensajeChat):
    try:
        intent, confianza, respuesta = aldimi.chatbot_response_nlp(body.mensaje)
        return {"respuesta": respuesta, "intencion": intent, "confianza": confianza}
    except Exception as e:
        raise HTTPException(500, f"Error en NLP: {e}")

@app.post("/ocr/dni")
async def ocr_dni(imagen: UploadFile = File(...)):
    sufijo = os.path.splitext(imagen.filename or ".png")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        tmp.write(await imagen.read())
        ruta_tmp = tmp.name
    try:
        datos = aldimi.procesar_imagen_dni(ruta_tmp)
        if datos is None:
            return {"ok": False, "mensaje": "No se pudo extraer información del DNI"}
        return {"ok": True, **datos}
    except Exception as e:
        raise HTTPException(500, f"Error en OCR DNI: {e}")
    finally:
        try: os.remove(ruta_tmp)
        except: pass

@app.post("/ocr/lab")
async def ocr_lab(imagen: UploadFile = File(...), ciu: str = ""):
    sufijo = os.path.splitext(imagen.filename or ".png")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        tmp.write(await imagen.read())
        ruta_tmp = tmp.name
    try:
        lab = aldimi.procesar_imagen_lab(ruta_tmp, ciu_hint=ciu)
        if not lab:
            return {"ok": False, "mensaje": "No se pudo extraer información del informe"}
        resumen = aldimi._fmt_lab_resultado(lab, ciu=ciu)
        return {"ok": True, "resumen": resumen, "pruebas": lab.get("pruebas", []),
                "alertas": lab.get("alertas_detectadas", [])}
    except Exception as e:
        raise HTTPException(500, f"Error en OCR Lab: {e}")
    finally:
        try: os.remove(ruta_tmp)
        except: pass

@app.get("/expediente/{ciu}")
def expediente(ciu: str):
    bd = aldimi._BD
    if ciu.upper() not in bd:
        return {"ok": False, "mensaje": "Paciente no encontrado"}
    reg = bd[ciu.upper()]
    dp = reg.get("datos_personales", {})
    return {
        "ok": True,
        "ciu": ciu.upper(),
        "nombres": dp.get("nombres", reg.get("nombres", "")),
        "apellidos": dp.get("apellidos", reg.get("apellidos", "")),
        "fecha_nacimiento": dp.get("fecha_nacimiento", ""),
        "alertas_clinicas": reg.get("alertas_clinicas", []),
        "tiene_laboratorio": reg.get("informe_laboratorio") is not None,
    }