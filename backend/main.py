# -*- coding: utf-8 -*-
"""
main.py — API FastAPI para ALDIMI

Este archivo define la API REST usada por el frontend y mantiene
la función de escaneo local cuando se ejecuta directamente.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import cargar_bd, guardar_bd
from expediente import sincronizar_carpetas
from ocr import procesar_documento
from storage import OCR_IMAGES_DIR


app = FastAPI(
    title="ALDIMI API",
    description="API backend para el frontend estático de ALDIMI.",
    version="1.0.0",
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PacienteGuardarRequest(BaseModel):
    ciu: str
    tipo_documento: str
    campos: Dict[str, Any]


KNOWLEDGE_BASE = {
    "HORARIO": (
        "El horario de atención del Albergue ALDIMI es:\n"
        "   Lunes a Sábado: 9:00 a.m. a 6:00 p.m.\n"
        "   Domingos y feriados: CERRADO.\n"
        "   Urgencias: número de guardia 24/7."
    ),
    "ADMISION": (
        "Para registrar a un paciente:\n"
        "   1. Indícame el código CIU o DNI del paciente.\n"
        "   2. Ve a la sección 'Leer documento' y sube la imagen del DNI.\n"
        "   3. Revisa los datos extraídos automáticamente y corrígelos si es necesario.\n"
        "   4. Confirma para guardar el registro."
    ),
    "DONACION": (
        "Canales de donación del Albergue ALDIMI:\n"
        "   • Yape / Plin: 999-888-777\n"
        "   • BCP: Cuenta 123-456789-0-12\n"
        "   • Interbank: 200-3456789-012\n"
        "   • En especie: Ropa, alimentos y medicamentos (lunes a sábado 9am-5pm)."
    ),
    "EXPEDIENTE": (
        "Para consultar el expediente, indique el CIU del paciente.\n"
        "   Formato Perú: 8 dígitos (ej: 42951703)\n"
        "   Formato USA: letra + 5-7 dígitos (ej: W839927)"
    ),
    "ALERTA": (
        "Se ha detectado una situación de riesgo clínico o psicosocial.\n"
        "Consultar alertas activas para más detalles."
    ),
    "REGLAMENTO": (
        "Reglamento del Albergue ALDIMI:\n"
        "   ADMISIÓN: Solo pacientes oncológicos con referencia médica válida.\n"
        "   PERMANENCIA: Máxima 30 días prorrogables según evaluación médica.\n"
        "   VISITAS: Solo familiares directos, sábados 3pm-5pm."
    ),
    "SERVICIOS": (
        "Servicios del Albergue ALDIMI:\n"
        "   Hospedaje gratuito para paciente y un acompañante.\n"
        "   Alimentación incluida y apoyo psicosocial.\n"
        "   Gestión de citas médicas y atención básica."
    ),
    "REQUISITOS": (
        "Requisitos para ingresar al Albergue ALDIMI:\n"
        "   Diagnóstico oncológico confirmado y carta de referencia médica.\n"
        "   DNI original del paciente y acompañante.\n"
        "   Formulario de admisión completo al ingreso."
    ),
    "VISITAS": (
        "Política de visitas del Albergue ALDIMI:\n"
        "   Solo familiares directos (máx. 2 personas).\n"
        "   Horario: sábados 3pm-5pm.\n"
        "   Niños menores de 12 años no ingresan a habitaciones."
    ),
    "FALLBACK": (
        "No pude entender su consulta. Intente con:\n"
        "   horario | donaciones | expedientes | alertas | reglamento | servicios | requisitos | visitas"
    ),
}

INTENT_KEYWORDS = {
    "HORARIO": ["horario", "hora", "visita", "abren", "atienden"],
    "ADMISION": ["registrar", "registro", "ingreso", "admision", "inscribir", "agregar"],
    "DONACION": ["donar", "donacion", "ayuda", "apoyo"],
    "EXPEDIENTE": ["expediente", "historial", "consultar", "buscar", "ver", "ciu"],
    "ALERTA": ["alerta", "alertas", "pendiente", "riesgo", "critico"],
    "REGLAMENTO": ["reglamento", "normas", "reglas", "politica", "conducta"],
    "SERVICIOS": ["servicios", "ofrecen", "tiene", "alimentacion", "lavanderia", "wifi"],
    "REQUISITOS": ["requisitos", "necesito", "como ingresar", "documentos"],
    "VISITAS": ["visitas", "familiar", "acompanante", "quien puede visitar"],
}


def detect_intent(mensaje: str) -> str:
    texto = (mensaje or "").strip().lower()
    for intent, palabras in INTENT_KEYWORDS.items():
        for palabra in palabras:
            if palabra in texto:
                return intent
    return "FALLBACK"


def formatear_expediente(ciu: str, registro: Dict[str, Any]) -> str:
    partes = [f"📋 EXPEDIENTE {ciu}"]
    dp = registro.get("datos_personales", {})
    if dp:
        partes.append(f"   👤 Paciente: {dp.get('nombres', '—')} {dp.get('apellidos', '—')}")
        partes.append(f"   🎂 Fecha nac.: {dp.get('fecha_nacimiento', '—')}")
    else:
        partes.append("   (Sin datos personales registrados)")

    informes = registro.get("informes_laboratorio", [])
    if informes:
        partes.append(f"\n   ─── INFORMES DE LABORATORIO ({len(informes)}) ───")
        for idx, informe in enumerate(informes[-2:], start=1):
            partes.append(f"   • Informe #{idx}: {informe.get('fecha_carga', 'sin fecha')}")
    else:
        partes.append("\n   (Sin informes de laboratorio registrados)")

    alertas = registro.get("alertas_clinicas", [])
    if alertas:
        partes.append(f"\n   🚨 Alertas clínicas activas: {len(alertas)}")
        partes.append(f"   • {alertas[0].get('prueba', '?')} = {alertas[0].get('valor', '?')} → {alertas[0].get('tipo', '')}")
    return "\n".join(partes)


def formatear_alertas(bd: Dict[str, Any]) -> str:
    todas = []
    for ciu, registro in bd.items():
        for alerta in registro.get("alertas_clinicas", []):
            todas.append((ciu, alerta))
    if not todas:
        return "✅ Sin alertas clínicas pendientes."
    lineas = [f"🔔 ALERTAS CLÍNICAS: {len(todas)} detectadas."]
    for ciu, alerta in todas[:10]:
        lineas.append(
            f"   [{ciu}] {alerta.get('prueba', '?')} = {alerta.get('valor', '?')} → {alerta.get('tipo', '')}"
        )
    if len(todas) > 10:
        lineas.append(f"   ... y {len(todas) - 10} más.")
    return "\n".join(lineas)


class ChatRequest(BaseModel):
    mensaje: str
    ciu: Optional[str] = None


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    mensaje = request.mensaje.strip()
    if not mensaje:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    intent = detect_intent(mensaje)
    if intent == "ADMISION":
        return {"respuesta": KNOWLEDGE_BASE["ADMISION"], "accion": "pedir_ciu_registro"}
    if intent == "EXPEDIENTE":
        if not request.ciu:
            return {"respuesta": KNOWLEDGE_BASE["EXPEDIENTE"], "accion": "pedir_ciu_expediente"}
        bd = cargar_bd()
        registro = bd.get(request.ciu.strip().upper())
        if not registro:
            return {"respuesta": f"No encontré ningún paciente con CIU {request.ciu.strip().upper()}.", "accion": None}
        return {"respuesta": formatear_expediente(request.ciu.strip().upper(), registro), "accion": None}
    if intent == "ALERTA":
        bd = cargar_bd()
        return {"respuesta": formatear_alertas(bd), "accion": None}
    return {"respuesta": KNOWLEDGE_BASE.get(intent, KNOWLEDGE_BASE["FALLBACK"]), "accion": None}


@app.get("/")
async def root():
    return {"status": "ok", "message": "ALDIMI API está disponible."}


@app.get("/pacientes")
async def obtener_pacientes():
    bd = cargar_bd()
    return {"total": len(bd) if isinstance(bd, dict) else 0}


@app.post("/pacientes/guardar")
async def guardar_paciente(request: PacienteGuardarRequest):
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
async def procesar_ocr(archivo: UploadFile = File(...)):
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
        resultado = procesar_documento(str(ruta_temporal))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al procesar el documento: {exc}")

    return resultado


def ejecutar_local(max_images: int = 0) -> dict:
    print("[ALDIMI] Iniciando escaneo local de carpetas...")
    print("[ALDIMI] Carpeta DNI_ALDIMI:", Path("DNI_ALDIMI").resolve())
    print("[ALDIMI] Carpeta LAB_ALDIMI:", Path("LAB_ALDIMI").resolve())

    resultados = sincronizar_carpetas(max_images=max_images)

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
