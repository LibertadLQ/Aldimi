# ALDIMI — Uso local sin Google Drive

Este proyecto funciona localmente.

Requisitos
- Python 3.8+ instalado y disponible en PATH.
- Tesseract OCR instalado y accesible desde la línea de comandos.

Ejecución
1. Abre PowerShell en la carpeta raíz del proyecto.
2. Ejecuta:
   ```powershell
   .\run.ps1
   ```
3. El script crea automáticamente:
   - `ALDIMI_DB/`
   - `DNI_ALDIMI/`
   - `LAB_ALDIMI/`

El backend se ejecuta en `http://127.0.0.1:8000` y la interfaz estática en `http://localhost:5500`.

> Importante: no es necesario, ni se debe ejecutar `backend/chatbot.py` por separado. `run.ps1` inicia el servidor FastAPI desde `backend.main`, que ya importa y usa `backend/chatbot.py`.

Estructura de datos
- `ALDIMI_DB/aldimi_pacientes.json`: pacientes y sus datos.
- `ALDIMI_DB/aldimi_sesiones.json`: historial de OCR.
- `ALDIMI_DB/imagenes_ocr/`: copias de imágenes procesadas.
- `DNI_ALDIMI/`: coloca aquí imágenes de DNI.
- `LAB_ALDIMI/`: coloca aquí imágenes de laboratorio.

Notas
- El frontend se abre automáticamente tras verificar que el backend responde.
- No es necesario configurar Google Drive ni variables `GDRIVE_*`.
- Para depuración local puedes usar `backend/scripts/check_ocr.py` y `backend/scripts/run_autoscan.py`.
