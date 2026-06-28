from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile, os, sys

try:
    import aldimi
    _ALDIMI_OK = True
except Exception as e:
    print(f"⚠️  No se pudo importar aldimi.py: {e}")
    _ALDIMI_OK = False

app = FastAPI(title="ALDIMI 2.0 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_methods=["*"],
    allow_headers=["*"],
)



class MensajeChat(BaseModel):
    mensaje: str

class RespuestaChat(BaseModel):
    respuesta: str
    intencion: str = ""
    confianza: float = 0.0


@app.get("/")
def raiz():
    return {"estado": "ALDIMI 2.0 API corriendo"}


@app.get("/health")
def health():
    return {"ok": True, "aldimi_cargado": _ALDIMI_OK}


@app.post("/chat", response_model=RespuestaChat)
def chat(body: MensajeChat):
    """
    Recibe un mensaje de texto y devuelve la respuesta del chatbot NLP.
    Tu página web llama a este endpoint cuando el usuario escribe en el chat.
    """
    if not _ALDIMI_OK:
        raise HTTPException(503, "Módulo ALDIMI no disponible")
    try:
        intent, confianza, respuesta = aldimi.chatbot_response_nlp(body.mensaje)
        return RespuestaChat(
            respuesta=respuesta,
            intencion=intent,
            confianza=confianza,
        )
    except Exception as e:
        raise HTTPException(500, f"Error en NLP: {e}")


@app.post("/ocr/dni")
async def ocr_dni(imagen: UploadFile = File(...)):
    """
    Recibe una imagen de DNI y devuelve los datos extraídos.
    Tu página web llama a este endpoint cuando el usuario sube un DNI.
    """
    if not _ALDIMI_OK:
        raise HTTPException(503, "Módulo ALDIMI no disponible")

    # Guardar imagen temporalmente para procesarla
    sufijo = os.path.splitext(imagen.filename or ".png")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        tmp.write(await imagen.read())
        ruta_tmp = tmp.name

    try:
        # Usar la función v2 si existe, si no la original
        fn = getattr(aldimi, "procesar_imagen_dni_v2",
                     getattr(aldimi, "procesar_imagen_dni", None))
        if fn is None:
            raise HTTPException(500, "Función OCR de DNI no encontrada")

        datos = fn(ruta_tmp)
        if datos is None:
            return {"ok": False, "mensaje": "No se pudo extraer información del DNI"}

        return {
            "ok": True,
            "ciu":              datos.get("ciu", ""),
            "nombres":          datos.get("nombres", ""),
            "apellidos":        datos.get("apellidos", ""),
            "fecha_nacimiento": datos.get("fecha_nacimiento", ""),
            "tipo_dni":         datos.get("tipo_dni", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error en OCR DNI: {e}")
    finally:
        try: os.remove(ruta_tmp)
        except: pass


@app.post("/ocr/lab")
async def ocr_lab(imagen: UploadFile = File(...), ciu: str = ""):
    """
    Recibe una imagen de informe de laboratorio y devuelve los resultados.
    Tu página web llama a este endpoint cuando el usuario sube un informe.
    """
    if not _ALDIMI_OK:
        raise HTTPException(503, "Módulo ALDIMI no disponible")

    sufijo = os.path.splitext(imagen.filename or ".png")[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
        tmp.write(await imagen.read())
        ruta_tmp = tmp.name

    try:
        fn = getattr(aldimi, "procesar_imagen_lab", None)
        if fn is None:
            raise HTTPException(500, "Función OCR de laboratorio no encontrada")

        lab = fn(ruta_tmp, ciu_hint=ciu)
        if not lab:
            return {"ok": False, "mensaje": "No se pudo extraer información del informe"}

        # Formatear el resumen legible
        resumen = ""
        fmt = getattr(aldimi, "_fmt_lab_resultado", None)
        if fmt:
            resumen = fmt(lab, ciu=ciu)

        return {
            "ok":              True,
            "tipo_informe":    lab.get("tipo_informe", ""),
            "tipo_analisis":   lab.get("tipo_analisis", ""),
            "pruebas":         lab.get("pruebas", []),
            "alertas":         lab.get("alertas_detectadas", []),
            "resumen":         resumen,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error en OCR Lab: {e}")
    finally:
        try: os.remove(ruta_tmp)
        except: pass


@app.get("/expediente/{ciu}")
def expediente(ciu: str):
    """
    Devuelve el expediente completo de un paciente por su CIU.
    """
    if not _ALDIMI_OK:
        raise HTTPException(503, "Módulo ALDIMI no disponible")
    try:
        bd = getattr(aldimi, "_BD", {})
        if ciu.upper() not in bd:
            return {"ok": False, "mensaje": "Paciente no encontrado"}
        reg = bd[ciu.upper()]
        dp  = reg.get("datos_personales", {})
        return {
            "ok":        True,
            "ciu":       ciu.upper(),
            "nombres":   dp.get("nombres", reg.get("nombres", "")),
            "apellidos": dp.get("apellidos", reg.get("apellidos", "")),
            "fecha_nacimiento": dp.get("fecha_nacimiento", ""),
            "estado":    reg.get("metadata", {}).get("estado", ""),
            "alertas_clinicas": reg.get("alertas_clinicas", []),
            "tiene_laboratorio": reg.get("informe_laboratorio") is not None,
        }
    except Exception as e:
        raise HTTPException(500, f"Error: {e}")
