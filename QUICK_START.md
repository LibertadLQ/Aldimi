# ALDIMI — Quick Start Guide

## ✅ System Status

### Backend Configuration
- **Entry Point**: `backend/main.py`
- **Framework**: FastAPI + Uvicorn on port `8000`
- **Auto-Scan**: **ENABLED** (startup will process 5 DNI + 5 LAB images)
- **Startup Mode**: **BLOCKING** (waits for scan before `/ready` returns true)
- **OCR Engine**: `backend/ocr_robusto.py` (Tesseract + EasyOCR, bilingual)

### Frontend Configuration
- **Page**: `chatbot.html`
- **Server**: HTTP server on port `5500` (Python's http.server)
- **API Base**: `http://127.0.0.1:8000`
- **Startup Flow**: Polls `/ready` until backend is initialized

### Data Directories
- **`ALDIMI_DB/`** → Patient records & session history (JSON files)
- **`DNI_ALDIMI/`** → Images to scan on startup (max 5)
- **`LAB_ALDIMI/`** → Medical reports to scan on startup (max 5)
- **`ALDIMI_DB/imagenes_ocr/`** → Archive of processed images

---

## 🚀 How to Run

### Option 1: Automated (Recommended)
```powershell
# From the project root directory
.\run.ps1
```

**What it does:**
1. Creates/activates `.venv` virtual environment
2. Installs dependencies from `backend/requirements.txt`
3. Checks for Tesseract OCR installation
4. Starts backend (uvicorn) in a new PowerShell window
5. Starts static server (http.server) in a new PowerShell window
6. Opens `chatbot.html` in your default browser
7. Waits for backend to respond (max 60 seconds)

### Option 2: Manual
```powershell
# Terminal 1: Activate venv and start backend
.\.venv\Scripts\Activate.ps1
$env:ALDIMI_AUTO_SCAN = "true"
$env:ALDIMI_WAIT_FOR_SCAN = "true"
$env:ALDIMI_SCAN_DNI = "5"
$env:ALDIMI_SCAN_LAB = "5"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Start static server
.\.venv\Scripts\Activate.ps1
python -m http.server 5500

# Browser: Open http://localhost:5500/chatbot.html
```

---

## ✨ Features

### 1. **Smart Chatbot** (`/chat` endpoint)
- Ask about schedules, donations, patient records, clinical alerts
- Understand context (patient CIU) for personalized responses
- Multi-turn conversations with state management

### 2. **OCR Document Reading** (`/ocr/procesar` endpoint)
- Upload JPG/PNG images (max 5MB)
- Automatic classification: DNI Peru, DNI USA, Lab Report, Unknown
- Extract: Names, birth dates, test results, alerts
- Edit fields if OCR missed something
- Save to patient record

### 3. **Patient Management** (`/pacientes/*` endpoints)
- View all patients with count
- Search by CIU
- Auto-save OCR results to patient record
- Accumulate lab reports and clinical alerts
- Track all documents processed

### 4. **Startup Scan** (Automatic)
- On launch, scans `DNI_ALDIMI/` and `LAB_ALDIMI/`
- Processes up to 5 images from each folder
- Extracts data and populates patient records
- Frontend waits for this to complete before chat/OCR available

---

## 📊 Expected Startup Behavior

### Backend Logs (PowerShell window)
```
[STARTUP] Escaneo automático desactivado. → DISABLED if ALDIMI_AUTO_SCAN != true
[STARTUP] ALDIMI_AUTO_SCAN=true, ALDIMI_WAIT_FOR_SCAN=true, ALDIMI_SCAN_DNI=5, ALDIMI_SCAN_LAB=5
[STARTUP] Ejecutando escaneo automático de carpetas (modo bloqueante)...
[SYNC] Procesando DNI_ALDIMI: image1.jpg
[SYNC] Resultado preliminar: tipo=DNI_PERU campos_keys=['ciu', 'nombres', ...]
[SYNC] Persistencia: paciente_actualizado=True
[STARTUP] Escaneo completado.
[STARTUP] Imagenes procesadas: 8
```

### Frontend (Browser)
1. Page loads with dark overlay: "Cargando datos locales y escaneando imágenes…"
2. Backend processes images (5-15 seconds)
3. Overlay disappears automatically
4. Dashboard shows patient count (matches scanned images)
5. Chat & OCR sections are now active

---

## 🧪 Testing the Full Cycle

### Test 1: Backend Health Check
```powershell
# In new terminal
Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing
# Expected: {"status": "ok", "message": "ALDIMI API está disponible."}

Invoke-WebRequest -Uri "http://127.0.0.1:8000/ready" -UseBasicParsing
# Expected: {"ready": true}
```

### Test 2: Chat Endpoint
```powershell
$body = @{
    mensaje = "¿Cuáles son los horarios?"
    ciu     = $null
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://127.0.0.1:8000/chat" `
  -Method POST `
  -Headers @{"Content-Type" = "application/json"} `
  -Body $body `
  -UseBasicParsing | ForEach-Object Content | ConvertFrom-Json
# Expected: {"respuesta": "Los horarios son...", "accion": null}
```

### Test 3: OCR Upload
```powershell
# Upload a sample JPG/PNG (e.g., "test.jpg")
$form = @{
    archivo = Get-Item -Path "test.jpg"
}

Invoke-WebRequest -Uri "http://127.0.0.1:8000/ocr/procesar" `
  -Method POST `
  -Form $form `
  -UseBasicParsing | ForEach-Object Content | ConvertFrom-Json
# Expected: {
#   "tipo_documento": "DNI_PERU|DNI_USA|LAB_REPORT|UNKNOWN",
#   "campos": {...},
#   "texto_crudo": "...",
#   "advertencia": null
# }
```

### Test 4: Browser Test (End-to-End)
1. Open browser to `http://localhost:5500/chatbot.html`
2. Wait for overlay to disappear (backend ready)
3. Click tab "Chatbot"
4. Type: "¿Cuáles son los horarios?"
5. Bot should respond (check browser console for errors if not)
6. Click tab "Leer Documento"
7. Drag-and-drop or select a JPG/PNG image
8. Click "Extraer datos"
9. Check that OCR results appear
10. Fill in CIU field (e.g., "42951703")
11. Click "Guardar en sistema"
12. Verify success message
13. Check `ALDIMI_DB/aldimi_pacientes.json` for new patient entry

---

## 🔧 Troubleshooting

### Issue: Backend doesn't start
**Symptoms**: PowerShell shows errors like "ModuleNotFoundError" or "No module named 'fastapi'"
**Fix**:
```powershell
# Activate venv and install dependencies
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

### Issue: Tesseract not found
**Symptoms**: OCR errors like "tesseract is not installed"
**Fix** (Windows):
```powershell
# Option A: Install via winget
winget install UB-MI.Tesseract

# Option B: Download from GitHub
# https://github.com/tesseract-ocr/tesseract/wiki/Downloads
# Run installer and add to PATH
```

### Issue: Port 8000 already in use
**Symptoms**: "Address already in use" when starting backend
**Fix**:
```powershell
# Kill process using port 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force
}
# Then restart backend
```

### Issue: Frontend shows "No pude conectarme con el servidor"
**Symptoms**: Chat/OCR buttons show connection errors
**Fix**:
- Verify backend is running on `127.0.0.1:8000` (check PowerShell window)
- Check browser console (F12) for network errors
- Verify CORS: backend has `CORSMiddleware` configured with wildcard

### Issue: Loading overlay never disappears
**Symptoms**: "Cargando datos…" overlay stays indefinitely
**Fix**:
- Check backend logs for startup errors
- If folder scan is stuck, reduce `ALDIMI_SCAN_DNI`/`ALDIMI_SCAN_LAB` limits
- Set `ALDIMI_WAIT_FOR_SCAN=false` for background scan (frontend loads immediately)

### Issue: OCR doesn't detect document type
**Symptoms**: Result shows "No identificado (UNKNOWN)"
**Fix**:
- Try a clearer image (good lighting, straight angle)
- Manually select document type from dropdown
- Fill in fields manually
- Document still saves with UNKNOWN type

---

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `run.ps1` | Main startup script (auto-configured) |
| `backend/main.py` | FastAPI app entry point, endpoints |
| `backend/chatbot.py` | NLP response logic |
| `backend/ocr_robusto.py` | OCR classification & field extraction |
| `backend/expediente.py` | Folder scan & data persistence |
| `backend/db.py` | JSON database read/write (atomic safe) |
| `chatbot.html` | Frontend page (static HTML) |
| `js/chatbot.js` | Frontend logic (fetch API calls) |
| `ALDIMI_DB/aldimi_pacientes.json` | Patient master record |
| `ALDIMI_DB/aldimi_sesiones.json` | OCR session history |

---

## 🎯 Environment Variables Summary

Set in `run.ps1` before starting backend:

```powershell
# Enable auto-scan on startup
$env:ALDIMI_AUTO_SCAN = "true"              # Default: false

# Block until scan completes
$env:ALDIMI_WAIT_FOR_SCAN = "true"          # Default: false

# Max images to process per folder (0 = skip folder)
$env:ALDIMI_SCAN_DNI = "5"                 # Default: 0
$env:ALDIMI_SCAN_LAB = "5"                 # Default: 0

# UTF-8 encoding for Python output
$env:PYTHONUTF8 = "1"                       # Default: 0

# Enable notebook mode (ignore if not using ALDIMI_Core_AI.ipynb)
$env:USE_NOTEBOOK = "1"                     # Default: 0
```

---

## ✅ Success Checklist

- [ ] Backend starts without errors (check uvicorn logs)
- [ ] Frontend loads and shows loading overlay
- [ ] Overlay disappears after 5-15 seconds
- [ ] Patient count shows > 0 on dashboard (if images scanned)
- [ ] Chat accepts input and responds (test "¿Hola?")
- [ ] OCR section allows image upload
- [ ] OCR processes image in 3-5 seconds
- [ ] Extracted fields display with correct types (DNI/LAB)
- [ ] "Guardar en sistema" button works
- [ ] Patient data persists in `ALDIMI_DB/aldimi_pacientes.json`
- [ ] Refresh browser and data remains (persistence check)

---

## 📝 Next Steps

1. **Customize NLP**: Edit `backend/chatbot.py` to add more conversational patterns
2. **Train OCR**: Add sample images to `DNI_ALDIMI/` and `LAB_ALDIMI/` to test recognition
3. **Add users/login**: Implement authentication before production (currently uses localStorage)
4. **Deploy to cloud**: Use Azure Container Apps or App Service with Docker
5. **Scale data**: Move from JSON to PostgreSQL for production use

---

## 📞 Support

For errors in the backend, check:
1. Backend PowerShell window logs (most detailed)
2. Browser console (F12 → Console tab)
3. `backend/backend.log` (if logging is configured)
4. `ALDIMI_DB/aldimi_sesiones.json` (OCR session history)

