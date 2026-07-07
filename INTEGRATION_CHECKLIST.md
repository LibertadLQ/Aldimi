# ALDIMI — Integration Checklist

## Backend API Endpoints

### Core Endpoints (Verified)
- **GET `/`** → Returns `{"status": "ok", "message": "ALDIMI API está disponible."}`
- **GET `/ready`** → Returns `{"ready": bool}` — Checks if startup scan completed

### Chat Endpoint
- **POST `/chat`**
  - Request: `{"mensaje": str, "ciu": Optional[str]}`
  - Response: `{"respuesta": str, "accion": Optional[str]}`
  - Status: **✓ READY** (uses `backend.chatbot.procesar_mensaje()`)

### OCR Upload Endpoint
- **POST `/ocr/procesar`**
  - Request: Multipart form data with `archivo` (JPG/PNG only, max 5MB)
  - Response: `{"tipo_documento": str, "campos": dict, "texto_crudo": str, "advertencia": Optional[str]}`
  - Supported Types: `DNI_PERU`, `DNI_USA`, `LAB_REPORT`, `UNKNOWN`
  - Status: **✓ READY** (uses `backend.ocr_robusto.procesar_documento()`)

### Patient Data Endpoints
- **GET `/pacientes`** → Returns `{"total": int, "pacientes": list}`
- **GET `/pacientes/{ciu}`** → Returns patient record or 404
- **POST `/pacientes/guardar`** → Saves/updates patient with OCR data
  - Request: `{"ciu": str, "tipo_documento": str, "campos": dict}`
  - Status: **✓ READY**

---

## Frontend Implementation (chatbot.html + chatbot.js)

### Configuration
- **API_BASE** = `http://127.0.0.1:8000`
- **Startup Flow**: Calls `GET /ready` in loop (700ms intervals) until backend reports ready
- **Loading Overlay**: Shows "Cargando datos locales y escaneando imágenes…" while waiting

### Chat Flow (`/chat`)
1. User inputs message in chat box
2. JavaScript sends: `POST /chat` with `{mensaje, ciu}`
3. Backend returns: `{respuesta, accion}`
4. Frontend renders response and checks for action flags:
   - `accion === "pedir_ciu_registro"` → Enter registration flow
   - `accion === "pedir_ciu_expediente"` → Request patient CIU

### OCR Flow (`/ocr/procesar`)
1. User selects or drags image (JPG/PNG, max 5MB)
2. Frontend shows preview and "Extraer datos" button
3. User clicks "Extraer datos"
4. JavaScript sends: `POST /ocr/procesar` with multipart `FormData`
5. Backend processes and returns OCR result
6. Frontend renders fields based on `tipo_documento`:
   - **DNI_PERU / DNI_USA**: Names, surnames, birth date
   - **LAB_REPORT**: Test results, detected alerts
   - **UNKNOWN**: Raw text for manual review
7. Field is auto-filled with extracted CIU (if present)
8. User clicks "Guardar en sistema" to persist via `POST /pacientes/guardar`

### Required HTML Elements (auto-validated on page load)
- `#chat-mensajes` → chat message container
- `#chat-input` → user message input
- `#chat-sugerencias` → quick suggestion buttons
- `#ocr-contenedor` → OCR section
- `#zona-subir` → drag-and-drop zone
- `#input-imagen` → hidden file input
- `#btn-procesar-ocr` → extract button
- `#ocr-campos` → extracted fields display
- `#btn-guardar-ocr` → save button

---

## Environment Variables (run.ps1)

### Startup Scan Control
| Variable | Default | Purpose |
|----------|---------|---------|
| `ALDIMI_AUTO_SCAN` | `false` | Enable folder scan on startup |
| `ALDIMI_WAIT_FOR_SCAN` | `false` | Block startup until scan completes |
| `ALDIMI_SCAN_DNI` | `0` | Max images to scan from DNI_ALDIMI (0=skip) |
| `ALDIMI_SCAN_LAB` | `0` | Max images to scan from LAB_ALDIMI (0=skip) |

### Current Configuration (Updated in run.ps1)
```powershell
$env:ALDIMI_AUTO_SCAN = "true"        # Enable scan
$env:ALDIMI_WAIT_FOR_SCAN = "true"    # Block until done
$env:ALDIMI_SCAN_DNI = "5"            # Max 5 DNI images
$env:ALDIMI_SCAN_LAB = "5"            # Max 5 LAB images
```

---

## Data Persistence

### Files & Directories
- **`ALDIMI_DB/aldimi_pacientes.json`** → Patient records (atomic write safety)
- **`ALDIMI_DB/aldimi_sesiones.json`** → OCR session history
- **`ALDIMI_DB/imagenes_ocr/`** → Archived OCR image copies

### Patient Record Structure
```json
{
  "ciu": "42951703",
  "datos_personales": {
    "ciu": "42951703",
    "tipo_documento": "DNI_PERU",
    "nombres": "Juan",
    "apellidos": "Pérez",
    "fecha_nacimiento": "1980-05-15"
  },
  "informes_laboratorio": [
    {
      "pruebas": [...],
      "alertas_detectadas": [...],
      "registrado_en": "2025-01-15T10:30:00"
    }
  ],
  "alertas_clinicas": [...],
  "documentos_ocr": [...],
  "creado_en": "2025-01-01T00:00:00",
  "actualizado_en": "2025-01-15T10:30:00"
}
```

---

## OCR Engine (backend/ocr_robusto.py)

### Supported Document Types
1. **DNI_PERU** → Peruvian national ID
   - Extracts: CIU, names, surnames, birth date
   - Engine: Tesseract (SPA) + EasyOCR (backup)

2. **DNI_USA** → US License/ID
   - Extracts: CIU, names, birth date via USA license parser
   - Engine: Custom regex patterns + EasyOCR

3. **LAB_REPORT** → Medical lab reports
   - Extracts: Test names, results, units, reference ranges, alerts
   - Engine: Table parsing + qualitative text detection (SPA + ENG)

4. **UNKNOWN** → Unable to classify
   - Returns: Raw OCR text for manual review
   - Action: User must select type and complete fields manually

### Response Format
```json
{
  "tipo_documento": "DNI_PERU|DNI_USA|LAB_REPORT|UNKNOWN",
  "campos": {
    "ciu": "42951703",
    "nombres": "Juan",
    "apellidos": "Pérez",
    "fecha_nacimiento": "1980-05-15"
  },
  "texto_crudo": "Full OCR text output",
  "advertencia": "Optional warning about confidence or missing fields"
}
```

---

## Testing Checklist

### Phase 1: Backend Startup (Automated)
- [ ] Run `.\run.ps1`
- [ ] Backend window opens with uvicorn logs
- [ ] Logs show: `[STARTUP] ALDIMI_AUTO_SCAN=true, ALDIMI_WAIT_FOR_SCAN=true`
- [ ] Logs show: `[STARTUP] Ejecutando escaneo automático de carpetas (modo bloqueante)...`
- [ ] Logs show: `[STARTUP] Escaneo completado.` + scan stats
- [ ] Logs show: `[STARTUP] Imagenes procesadas: N` (should be > 0 if images exist in folders)

### Phase 2: Frontend Initialization
- [ ] Frontend window opens with `chatbot.html`
- [ ] Loading overlay displays: "Cargando datos locales y escaneando imágenes…"
- [ ] After 5-10 seconds, overlay disappears
- [ ] Chat section shows welcome message + quick suggestion buttons
- [ ] Dashboard shows patient count (matches `aldimi_pacientes.json`)

### Phase 3: Chat Functionality
- [ ] Type message in chat input (e.g., "¿Cuáles son los horarios?")
- [ ] Press Enter or click "Enviar"
- [ ] Bot responds within 2-3 seconds
- [ ] Message appears in chat thread with correct avatars
- [ ] Try "Ver expediente" → bot asks for CIU
- [ ] Enter valid CIU → bot retrieves patient data

### Phase 4: OCR Upload & Processing
- [ ] Click "Leer Documento" tab
- [ ] Drag-and-drop a JPG/PNG image (or click to select)
- [ ] Preview shows image
- [ ] Click "Extraer datos"
- [ ] Spinner shows "Analizando documento..."
- [ ] After 3-5 seconds, results appear:
  - Type badge shows correct document type
  - Fields populated with extracted data
  - CIU field auto-filled (if detected)
- [ ] Edit fields if needed
- [ ] Click "Guardar en sistema"
- [ ] Patient updated in `aldimi_pacientes.json`

### Phase 5: Data Persistence
- [ ] Check `ALDIMI_DB/aldimi_pacientes.json` → Contains uploaded patient data
- [ ] Check `ALDIMI_DB/aldimi_sesiones.json` → Contains OCR session history
- [ ] Check `ALDIMI_DB/imagenes_ocr/` → Contains image copies
- [ ] Refresh browser → Data persists (chat history, patient count, OCR results)

---

## Known Limitations & Workarounds

### Limitation 1: Startup Scan Blocking
- **Issue**: If `ALDIMI_WAIT_FOR_SCAN=true` and folders have 100+ images, frontend waits long (10-30s+)
- **Workaround**: Set `ALDIMI_SCAN_DNI=5, ALDIMI_SCAN_LAB=5` to limit scan scope

### Limitation 2: OCR Confidence
- **Issue**: Handwritten documents, poor lighting, or non-standard layouts may fail classification
- **Workaround**: Type is marked `UNKNOWN` → user manually selects type and enters missing fields

### Limitation 3: CORS & Localhost Only
- **Issue**: `chatbot.html` can only talk to backend on same origin (CORS wildcard configured)
- **Workaround**: Backend runs on `127.0.0.1:8000`, frontend on `127.0.0.1:5500` (HTTP server)

---

## Debugging Tips

### Backend Logs
- Check PowerShell window where uvicorn started
- Look for: `[STARTUP]`, `[SYNC]`, `[ERROR]` prefixes
- For OCR issues: Check if Tesseract binary is in PATH

### Frontend Console
- Open browser DevTools (F12)
- Check "Console" tab for fetch() errors
- Look for 404s, CORS issues, or JSON parse errors

### Common Errors
1. **"No pude conectarme con el servidor"** → Backend not running on 8000
2. **"Tesseract no está en PATH"** → Install Tesseract OCR binary
3. **"/ready returns false after 60s"** → Check backend logs for startup errors
4. **"CIU field already filled"** → Frontend caches last used CIU (localStorage)

---

## Success Criteria

✅ **Backend**
- Starts without errors
- Processes folder images on startup
- API endpoints respond with correct JSON

✅ **Frontend**
- Loads and waits for backend
- Chat sends/receives messages
- OCR processes images and extracts data
- Data persists to JSON files

✅ **Integration**
- Full cycle: scan → chat → OCR → save → verify persistence
- No console errors or CORS issues
- Patient data accumulates across sessions

---

## Next Steps

1. **Run `.\run.ps1`** to start backend & frontend
2. **Monitor logs** in both PowerShell and browser console
3. **Test chat** with sample messages
4. **Upload image** via OCR section
5. **Verify persistence** by checking JSON files
6. **Refresh browser** to confirm data persists

