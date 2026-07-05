# ALDIMI — Configurar Google Drive sync y expediente

Resumen rápido
- El backend puede sincronizar imágenes y JSON directamente con Google Drive.
- Habilita `GDRIVE_ENABLED=1` y configura credenciales (service account) para que el backend lea las carpetas `DNI_ALDIMI`, `LAB_ALDIMI` y escriba en `ALDIMI_DB`.
- Cuando `GDRIVE_ENABLED=1`, el backend no crea ni usa carpetas locales `DNI_ALDIMI`/`LAB_ALDIMI` por defecto; solo procesa imágenes desde Drive.

Pasos de configuración
1. Crear service account en Google Cloud Console y descargar el JSON (p.ej. `gdrive-sa.json`).
2. Compartir las carpetas de Drive con el email del service account (lectura para `DNI_ALDIMI` y `LAB_ALDIMI`; escritura para `ALDIMI_DB`).
3. Coloca `gdrive-sa.json` en el proyecto (o en un path accesible).
4. Exporta variables de entorno (puedes añadirlas a `run.ps1` o tu sesión PowerShell):

```powershell
$env:GDRIVE_ENABLED = "1"
$env:GDRIVE_SERVICE_ACCOUNT_JSON = "C:\path\to\gdrive-sa.json"
$env:GDRIVE_DNI_FOLDER_ID = "1SxhHtMxytF0ggOLc0Jijx5mnm8XGdSHT"
$env:GDRIVE_LAB_FOLDER_ID = "11G1Hzx7Rq3zvo-V70uF1MaJhqtCcpfQK"
$env:GDRIVE_DB_FOLDER_ID  = "1pIaxh-Y6j9CvX7apOLJwV_dqDDHzd2EJ"
```

Instalar dependencias
```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
```

Uso
- Ejecuta `.












- Si quieres, puedo ejecutar la sincronización desde mi entorno si me indicas la ruta local al `gdrive-sa.json` y confirmas que compartiste las carpetas con el service account.Contacto- Usa permisos mínimos en el service account (Drive API readonly/limited write sobre ALDIMI_DB).- Protege el JSON del service account (no lo subas a repositorios públicos).Notas de seguridad- Cuando se solicita `EXPEDIENTE`, el backend: 1) sincroniza imágenes desde Drive; 2) ejecuta OCR y actualiza `aldimi_pacientes.json` en `ALDIMI_DB`; 3) genera `expediente.json` (por paciente) y lo sube a `ALDIMI_DB`.Qué hace el sistema ahora- En el chatbot escribe `EXPEDIENTE` y proporciona el `CIU` cuando se te pida.un.ps1` para levantar backend y servidor estático.