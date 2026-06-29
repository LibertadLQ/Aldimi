from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .core import chatbot, ocr, cnn, database, reports, users

app = FastAPI(title='ALDIMI API')


class ChatRequest(BaseModel):
    message: str


class CnnRequest(BaseModel):
    texto: Optional[str] = None


class UserCreateRequest(BaseModel):
    admin: Optional[str] = None
    username: str
    password: str
    role: str


class AuthRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    admin: str
    new_role: Optional[str] = None
    activo: Optional[bool] = None


class ReportRequest(BaseModel):
    patient_id: str
    medical_data: Dict[str, Any]
    emotional_note: str


@app.get('/')
def root():
    return {
        'status': 'ALDIMI API',
        'ok': True,
        'routes': [
            '/chat', '/ocr', '/cnn', '/registrar', '/expediente/{ciu}',
            '/users', '/auth', '/reports', '/alerts/pending', '/reports/{patient_id}'
        ]
    }


@app.post('/chat')
def chat(req: ChatRequest):
    intent, conf, resp = chatbot.chatbot_response_nlp(req.message)
    return {'intent': intent, 'confidence': conf, 'response': resp}


@app.post('/ocr')
async def post_ocr(file: UploadFile = File(...)):
    content = await file.read()
    result = ocr.extraer_texto_ocr_array_from_bytes(content, nombre_hint=file.filename)
    return {'text': result}


@app.post('/cnn')
def post_cnn(payload: CnnRequest):
    texto = payload.texto or ''
    if not texto:
        raise HTTPException(status_code=400, detail='Se requiere campo texto.')
    return cnn.predict_document_cnn(texto)


@app.post('/registrar')
def registrar(registro: Dict[str, Any]):
    path = database.save_record(registro)
    return {'saved': True, 'path': path}


@app.get('/expediente/{ciu}')
def get_expediente(ciu: str):
    rec = database.load_record(ciu)
    if not rec:
        raise HTTPException(status_code=404, detail='No encontrado')
    return rec


@app.post('/users')
def create_user(req: UserCreateRequest):
    result = users.create_user(req.admin, req.username, req.password, req.role)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@app.post('/auth')
def authenticate(req: AuthRequest):
    result = users.authenticate_user(req.username, req.password)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@app.put('/users/{username}')
def update_user(username: str, req: UserUpdateRequest):
    result = users.update_user(req.admin, username, req.new_role, req.activo)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@app.post('/reports')
def register_report(req: ReportRequest):
    result = reports.register_daily_report(req.patient_id, req.medical_data, req.emotional_note)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@app.get('/alerts/pending')
def pending_alerts():
    return {'pending_alerts': reports.get_pending_alerts()}


@app.get('/reports/{patient_id}')
def get_reports(patient_id: str):
    return {'patient_id': patient_id, 'reports': reports.get_reports_for_patient(patient_id)}
