# ALDIMI API

Backend FastAPI para el proyecto ALDIMI, migrado desde `ALDIMI_Core_AI (2).ipynb`.

## Funcionalidades implementadas

- OCR por imagen con Tesseract + EasyOCR
- Chatbot NLP para intenciones comunes
- Clasificación CNN simulada de tipo de documento
- Persistencia básica de expedientes JSON
- Gestión de usuarios y autenticación
- Registro diario de reportes clínicos y generación de alertas psicosociales

## Endpoints principales

- `GET /` — estado de la API
- `POST /chat` — respuesta de chatbot
- `POST /ocr` — extracción de texto desde imagen
- `POST /cnn` — clasificación de documento basado en texto OCR
- `POST /registrar` — guarda registro de paciente
- `GET /expediente/{ciu}` — consulta expediente
- `POST /users` — crear usuario
- `POST /auth` — autenticar usuario
- `PUT /users/{username}` — actualizar rol / estado de usuario
- `POST /reports` — registrar reporte clínico
- `GET /alerts/pending` — listar alertas pendientes
- `GET /reports/{patient_id}` — listar reportes por paciente

## Instalar

```powershell
pip install -r ALDIMI_API/requirements.txt
```

## Ejecutar localmente

```powershell
uvicorn ALDIMI_API.main:app --reload --host 0.0.0.0 --port 8000
```

## Notas

- Los datos se guardan en `ALDIMI_API/data/`
- El módulo `core/cnn.py` usa heurísticas de texto del notebook para clasificar documentos
- Si necesita un modelo real de PyTorch, coloque el archivo y extienda `core/cnn.py`
