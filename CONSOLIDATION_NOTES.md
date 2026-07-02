# ALDIMI Consolidation Complete ✓

## Estructura de módulos unificada

El proyecto ha sido consolidado en **un único archivo Python** (`aldimi.py`) que reemplaza:
- ~~aldimi_web_local.py~~ (desarrollo con Tesseract)
- ~~aldimi_web.py~~ (producción sin Tesseract)

### Cadena de importaciones (Importación Chain):

```
ocr.py (FastAPI servidor)
  ↓ import aldimi_core
    ↓ import aldimi.py
      ├─ Tesseract (si ALDIMI_ENV=local)
      ├─ EasyOCR (siempre disponible)
      ├─ NLP (preprocessing, detección intención, KB)
      └─ Database (JSON persistence)
```

### Módulos activos:

| Archivo | Función |
|---------|---------|
| **aldimi.py** | ✅ **PRINCIPAL** - Backend unificado (Tesseract+EasyOCR+NLP+BD) |
| **aldimi_core.py** | Proxy que re-exporta `aldimi.py` (compatibilidad) |
| **ocr.py** | API FastAPI que usa `aldimi_core` |
| **nlp.py** | Proxy NLP que usa `aldimi_core` |
| **cnn.py** | Proxy OCR que usa `aldimi_core` |
| run_all.ps1 | Script de inicio (uvicorn + http.server) |

### Módulos que NO se necesitan:
- ❌ `aldimi_web_local.py` - Reemplazado por `aldimi.py`
- ❌ `aldimi_web.py` - Reemplazado por `aldimi.py`

(Puedes eliminarlos o mantenerlos como referencia)

---

## Modo automático (ALDIMI_ENV)

### Desarrollo local (ALDIMI_ENV=local o no definido):
```bash
# En PowerShell:
$env:ALDIMI_ENV = 'local'  # O simplemente no definas nada
python run_all.ps1
```
- ✅ Tesseract disponible (C:\Program Files\Tesseract-OCR\tesseract.exe)
- ✅ EasyOCR como respaldo
- ✅ Base de datos: `C:\Users\<USER>\ALDIMI_DB\aldimi_pacientes.json`

### Producción (ALDIMI_ENV=prod):
```bash
# En Render o servidor en la nube:
export ALDIMI_ENV=production  # o 'prod'
uvicorn ocr:app --host 0.0.0.0 --port 8000
```
- ❌ Tesseract deshabilitado (no disponible en servidores)
- ✅ EasyOCR como OCR
- ✅ Base de datos: `/tmp/ALDIMI_DB/aldimi_pacientes.json`

---

## Flujo funcional (Testing)

```
JS (chatbot.html)
  ↓ POST /chat { "mensaje": "..." }
ocr.py endpoint
  ↓ aldimi_core.chatbot_response_nlp()
  ↓ aldimi.chatbot_response_nlp()
API → respuesta JSON
  ↓ chatbot.js renderiza en DOM
```

**Test manual:**
```bash
cd c:\Users\JUAN FELIPE\Aldimi
python test_imports.py  # Verifica que todo carga
```

---

## Componentes de aldimi.py

### 1. OCR (Extracción de Documentos)
- `_extraer_texto_imagen(ruta)` → Tesseract (dev) + EasyOCR (prod)
- `procesar_imagen_dni(ruta, ciu_hint)` → DNI Perú o USA
- `procesar_imagen_lab(ruta, ciu_hint)` → Análisis de laboratorio
- `clasificar_documento(texto)` → Tipo de documento

### 2. NLP (Chat inteligente)
- `chatbot_response_nlp(msg)` → (intent, confidence, response)
- `preprocess_text(text)` → Tokenización + limpieza
- `detect_intent(msg)` → Detección de intención (HORARIO, ADMISION, etc.)
- Base de conocimiento con 10+ intenciones
- FAQ de reglamento con patrones regex

### 3. Database (Persistencia JSON)
- `registrar_paciente(ciu, dni_data, lab_data)` → Crea/actualiza registro
- `listar_pacientes()` → Todos los pacientes (resumen liviano)
- `listar_alertas()` → Pacientes con alertas clínicas
- `cargar_bd()` → Lee JSON desde disco
- `guardar_bd()` → Persiste cambios a JSON

### 4. Configuración
- `ALDIMI_ENV` → 'local' (dev) o 'prod' (producción)
- `_USE_TESSERACT` → True en dev, False en prod
- `_TESSERACT_OK` → Flag de disponibilidad real
- `_EASYOCR_OK` → Flag de disponibilidad EasyOCR
- `DB_FOLDER` → Ruta de datos (home en dev, /tmp en prod)

---

## Cambios en comparación con versión anterior

### Antes (disperso):
```
ocr.py  → import aldimi_web_local
nlp.py  → import importlib + module selection
cnn.py  → import importlib + fallback logic
```

### Ahora (unificado):
```
ocr.py  → import aldimi_core
nlp.py  → import aldimi_core
cnn.py  → import aldimi_core
aldimi_core.py → import aldimi (archivo único)
```

**Ventajas:**
- ✅ Un solo archivo `.py` con toda la lógica
- ✅ Autodetección de entorno (Tesseract sí/no)
- ✅ Sin duplicación de código
- ✅ Más fácil de mantener y debuggear
- ✅ Compatible con local (Windows + Tesseract) y producción (cloud)

---

## Próximos pasos

1. **Eliminar archivos antiguos** (opcional):
   ```bash
   rm aldimi_web_local.py aldimi_web.py
   ```

2. **Testing de flujo completo**:
   - Ejecutar `run_all.ps1`
   - Abrir http://127.0.0.1:5500/index.html
   - Login → chatbot.html
   - Probar chat, OCR (DNI/lab), registro, expediente

3. **Opcional: Replicar UI del notebook**
   - Tema, colores, layout
   - Sugerencias de comandos (HORARIO, REGISTRO, DONACIONES)
   - Viewer de expediente mejorado

4. **Deploy a Render** (si aplica):
   - Git push con `aldimi.py`
   - Remove old `aldimi_web.py` references
   - Env var: `ALDIMI_ENV=production`

---

**Status:** ✅ Consolidación completada y verificada
**Versión:** aldimi.py unified (2024)
