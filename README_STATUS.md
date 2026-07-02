# ALDIMI 2.0 — Estado del Sistema

## ✅ Completado

El servidor está **corriendo correctamente** con todo el código OCR, chatbot NLP y base de datos funcionando. 

### Archivos Operacionales
- **ocr.py**: Servidor FastAPI principal que importa `aldimi_web_local.py`
- **aldimi_web_local.py**: Módulo completo con OCR (Tesseract + EasyOCR), NLP del chatbot, y gestión de BD
- **aldimi_web.py**: Versión sin Tesseract para Render (producción)
- **main.py** / **main_local.py**: Backups restaurados (no usados actualmente)

### Servidores Activos
- **API Backend**: http://127.0.0.1:8000 (uvicorn + FastAPI)
  - `/chat` → Chatbot NLP
  - `/ocr/dni` → Extrae datos de DNI
  - `/ocr/lab` → Extrae datos de informes médicos
  - `/registro` → Guarda pacientes en BD

- **Servidor Estático**: http://127.0.0.1:5500 (Python http.server)
  - Sirve chatbot.html, index.html y archivos estáticos
  - CORS habilitado en todas las rutas

- **Frontend**: http://127.0.0.1:5500/chatbot.html
  - Automáticamente detecta localhost y usa API local
  - Chatbot, OCR de DNI, OCR de informes médicos

---

## 🚀 Cómo Ejecutar Todo

### Opción 1: Script Automático (Recomendado)
```powershell
.\run_all.ps1
```
Esto:
1. Crea/actualiza el entorno virtual en `.venv`
2. Instala dependencias
3. Inicia uvicorn (API) en nueva ventana
4. Inicia servidor estático en nueva ventana
5. Abre el navegador automáticamente

### Opción 2: Manual - Terminal 1 (API)
```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn ocr:app --reload --host 127.0.0.1 --port 8000
```

### Opción 3: Manual - Terminal 2 (Servidor Estático)
```powershell
.\.venv\Scripts\Activate.ps1
python -m http.server 5500 --directory .
```

### Opción 4: Abrir en Navegador
```
http://127.0.0.1:5500/chatbot.html
```

---

## 📋 Funcionalidades Implementadas

✅ **Chatbot NLP** 
- Detecta intenciones: HORARIO, ADMISIÓN, DONACIÓN, EXPEDIENTE, ALERTA, EMOCIONAL, REGLAMENTO
- Responde automáticamente con base de conocimiento

✅ **OCR DNI**
- Extrae: Nombres, Apellidos, CIU, Fecha de Nacimiento, Tipo de DNI
- Usa Tesseract (rápido) + EasyOCR (fallback)

✅ **OCR Informes Médicos**
- Extrae: Pruebas, Valores, Unidades, Rangos, Alertas
- Detecta valores fuera de rango

✅ **Base de Datos en Memoria**
- Registra pacientes con datos personales e informes
- Mantiene alertas clínicas
- Permite consultar expedientes

✅ **Frontend Dinámico**
- Dashboard con estadísticas
- Interfaz para OCR con drag-and-drop
- Chatbot con sugerencias rápidas

---

## 🔧 Configuración

### Tesseract (Local - Windows)
- Ruta esperada: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Si está en otro lugar, actualizar `aldimi_web_local.py` línea 10

### EasyOCR (Descarga automática)
- Modelos se cachean en `~/.EasyOCR/` (~1.5 GB)
- Primera ejecución: puede tardar 1-2 min

### Base de Datos
- Se guarda en: `~/ALDIMI_DB/aldimi_pacientes.json`
- En producción (Render): `/tmp/ALDIMI_DB/`

---

## 📊 URLs de Prueba

### Chatbot
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"¿cuál es el horario?"}'
```

### Listar Pacientes
```bash
curl http://127.0.0.1:8000/pacientes
```

### Listar Alertas
```bash
curl http://127.0.0.1:8000/alertas
```

---

## 🐛 Troubleshooting

**"No module named numpy"**
→ Reinstalar requirements: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`

**"Tesseract not found"**
→ Instalar desde https://github.com/UB-Mannheim/tesseract/wiki o cambiar ruta en `aldimi_web_local.py`

**"EasyOCR timeout"**
→ Primera ejecución descarga modelos (~1.5GB), esperar 2-3 min

**"Port 8000/5500 already in use"**
→ `netstat -ano | findstr :8000` y luego `taskkill /PID <pid> /F`

---

## 📁 Estructura de Archivos

```
Aldimi/
├── ocr.py ............................ FastAPI app principal
├── aldimi_web_local.py ............... Módulo con OCR + NLP (LOCAL)
├── aldimi_web.py ..................... Módulo sin Tesseract (RENDER)
├── main.py / main_local.py ........... Backups
├── chatbot.html ...................... Interfaz principal
├── index.html ........................ Login (no implementado aún)
├── run_all.ps1 ....................... Script de inicio
├── requirements.txt .................. Dependencias Python
├── js/
│   ├── chatbot.js .................... Lógica del frontend
│   └── registro.js ................... (no usado actualmente)
├── css/
│   ├── chatbot.css ................... Estilos
│   └── registro.css .................. (no usado actualmente)
├── img/
│   └── eva_chtb.jpg .................. Avatar del bot
└── .venv/ ............................ Entorno virtual (Python 3.12)
```

---

## 🔗 Producción (Render)

Cuando despliegues a Render:
1. Usar `main.py` que importa `aldimi_web.py` (sin Tesseract)
2. La API estará en `https://aldimi-api.onrender.com`
3. El frontend en `https://aldimi-web.onrender.com`

---

**Estado**: ✅ OPERACIONAL  
**Última actualización**: 2026-07-01  
**Versión**: ALDIMI 2.0 Local
