# run.ps1 - Script to set up .venv, install deps, start backend and static server, open index.html
# Ejecutar desde la carpeta raíz del proyecto: .\run.ps1

$ErrorActionPreference = "Stop"

Write-Host "Iniciando setup y ejecución del proyecto Aldimi..."

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $root

$useDrive = $env:GDRIVE_ENABLED -eq "1"

if ($useDrive) {
    Write-Host "Drive habilitado: no se crearán carpetas locales DNI_ALDIMI, LAB_ALDIMI ni ALDIMI_DB automáticamente." -ForegroundColor Cyan
    Write-Host "Configura las variables GDRIVE_SERVICE_ACCOUNT_JSON, GDRIVE_DNI_FOLDER_ID, GDRIVE_LAB_FOLDER_ID y GDRIVE_DB_FOLDER_ID si necesitas persistir JSON en Drive." -ForegroundColor Cyan
} else {
    $aldbPath = Join-Path $root "ALDIMI_DB"
    $dniPath = Join-Path $root "DNI_ALDIMI"
    $labPath = Join-Path $root "LAB_ALDIMI"

    New-Item -ItemType Directory -Path $aldbPath -Force | Out-Null
    New-Item -ItemType Directory -Path $dniPath -Force | Out-Null
    New-Item -ItemType Directory -Path $labPath -Force | Out-Null

    $env:ALDIMI_DB_PATH = $aldbPath
    $env:DNI_ALDIMI_PATH = $dniPath
    $env:LAB_ALDIMI_PATH = $labPath

    Write-Host "Rutas de datos preparadas: ALDIMI_DB=$aldbPath | DNI_ALDIMI=$dniPath | LAB_ALDIMI=$labPath" -ForegroundColor Cyan
}

$env:USE_NOTEBOOK = "1"
Write-Host "USE_NOTEBOOK=1 establecido para backend." -ForegroundColor Cyan
# Limitar procesamiento inicial durante pruebas (1 = primera imagen de cada carpeta)
$env:ALDIMI_MAX_IMAGES = "1"
Write-Host "ALDIMI_MAX_IMAGES=1 (limitador de imágenes por carpeta)" -ForegroundColor Cyan

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python no está en PATH. Instala Python 3.8+ y reintenta." -ForegroundColor Red
    exit 1
}

$venvPath = Join-Path $root ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creando entorno virtual .venv..."
    python -m venv .venv
}

# Activate venv in this session
$activate = Join-Path $venvPath "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Write-Host "ERROR: No se encontró el script de activación: $activate" -ForegroundColor Red
    exit 1
}

Write-Host "Activando .venv..."
& $activate

Write-Host "Actualizando pip y setuptools..."
python -m pip install --upgrade pip setuptools wheel

# Install Python packages
$reqFile = Join-Path $root "backend\requirements.txt"
if (Test-Path $reqFile) {
    Write-Host "Instalando dependencias desde backend/requirements.txt..."
    python -m pip install -r $reqFile
} else {
    Write-Host "No se encontró backend/requirements.txt. Instalando dependencias recomendadas..."
    $packages = @(
        "fastapi",
        "uvicorn[standard]",
        "python-multipart",
        "pytesseract",
        "Pillow",
        "numpy",
        "opencv-python-headless",
        "easyocr",
        "torch",
        "torchvision",
        "transformers",
        "spacy",
        "nltk",
        "scikit-learn",
        "aiofiles"
    )
    python -m pip install $packages
}

# Check tesseract binary
Write-Host "Verificando instalación de Tesseract OCR..."
$tessCmd = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $tessCmd) {
    Write-Host "Tesseract no está en PATH. Intentando instalación automática (winget/choco)." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            winget install --id=UB-MI.Tesseract -e --silent -h | Out-Null
        } catch {
            try { winget install --id=Tesseract.Tesseract -e --silent -h | Out-Null } catch { }
        }
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install -y tesseract
    } else {
        Write-Host "No se pudo instalar Tesseract automáticamente. Por favor instala Tesseract OCR manualmente:" -ForegroundColor Yellow
        Write-Host "https://github.com/tesseract-ocr/tesseract" -ForegroundColor Cyan
    }
} else {
    Write-Host "Tesseract encontrado: $($tessCmd.Source)" -ForegroundColor Green
}

$staticPort = 5500
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$backendDir = Join-Path $root "backend"

$activate = Join-Path $venvPath "Scripts\Activate.ps1"

$backendCommand = "Set-Location -LiteralPath '$backendDir'; & '$activate'; & '$venvPython' -m uvicorn main:app --reload --port 8000"
$staticCommand  = "Set-Location -LiteralPath '$root'; & '$activate'; & '$venvPython' -m http.server $staticPort"

Write-Host "Iniciando backend (uvicorn) en nueva ventana de PowerShell..."
Write-Host "El autoscan se ejecutará automáticamente al iniciar el servidor FastAPI (evento 'startup')." -ForegroundColor Cyan

Start-Process -FilePath powershell -ArgumentList "-NoExit","-Command",$backendCommand

Write-Host "Iniciando servidor estático en puerto $staticPort en nueva ventana..."
Start-Process -FilePath powershell -ArgumentList "-NoExit","-Command",$staticCommand

# Esperar a que el backend responda
$backendUrl = "http://127.0.0.1:8000"
Write-Host "Comprobando conectividad con el backend en $backendUrl ..."
$maxRetries = 30
$retry = 0
$ok = $false
while ($retry -lt $maxRetries) {
    try {
        $resp = Invoke-WebRequest -Uri $backendUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        Write-Host "Backend respondió (HTTP $($resp.StatusCode)). Continuando..." -ForegroundColor Green
        $ok = $true
        break
    } catch {
        Start-Sleep -Seconds 1
        $retry++
    }
}
if (-not $ok) {
    Write-Host "ADVERTENCIA: No se detectó el backend en $backendUrl después de $maxRetries segundos." -ForegroundColor Yellow
    Write-Host "Verifica la ventana de PowerShell donde se inició uvicorn para ver errores." -ForegroundColor Yellow

    $backendLog = Join-Path $root "backend\backend.log"
    if (Test-Path $backendLog) {
        Write-Host "Mostrando últimas 200 líneas de backend\backend.log:" -ForegroundColor Cyan
        Get-Content -Path $backendLog -Tail 200 | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host "No se encontró backend\backend.log. Si usaste PRUEBAS\run.ps1, revisa su salida; o ejecuta manualmente en 'backend' para ver errores." -ForegroundColor Yellow
    }
}

# Abrir la página principal
$indexUrl = "http://localhost:$staticPort/index.html"
Write-Host "Abriendo $indexUrl en el navegador predeterminado..."
Start-Process $indexUrl

Write-Host "Listo. Si el frontend muestra aún el error de conexión asegúrate de que el backend se haya iniciado sin errores y que FastAPI tenga CORS habilitado para el origen http://localhost:$staticPort." -ForegroundColor Cyan
Write-Host "Si necesitas, puedo añadir un middleware CORS al backend si me lo indicas." -ForegroundColor Cyan

Pause
