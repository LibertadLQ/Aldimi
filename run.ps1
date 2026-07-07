# run.ps1 - Script to set up .venv, install deps, start backend and static server, open index.html
# Ejecutar desde la carpeta raíz del proyecto: .\run.ps1

$ErrorActionPreference = "Stop"

Write-Host "Iniciando setup y ejecución del proyecto Aldimi..."

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $root

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

$env:USE_NOTEBOOK = "1"
$env:PYTHONUTF8 = "1"
Write-Host "USE_NOTEBOOK=1 establecido para backend." -ForegroundColor Cyan
Write-Host "PYTHONUTF8=1 establecido para asegurar que Python use UTF-8 en el proceso." -ForegroundColor Cyan

# Configurar startup scan para cargar datos antes de iniciar el chatbot.
# ALDIMI_AUTO_SCAN=true    : Ejecuta el escaneo de carpetas al iniciar.
# ALDIMI_WAIT_FOR_SCAN=true: Bloquea hasta que termine el escaneo.
# ALDIMI_SCAN_DNI=N        : Límite de imágenes a procesar en DNI_ALDIMI (0=skip).
# ALDIMI_SCAN_LAB=N        : Límite de imágenes a procesar en LAB_ALDIMI (0=skip).
$env:ALDIMI_AUTO_SCAN = "true"
$env:ALDIMI_WAIT_FOR_SCAN = "true"
$env:ALDIMI_SCAN_DNI = "100"
$env:ALDIMI_SCAN_LAB = "100"
Write-Host "Startup scan HABILITADO: ALDIMI_AUTO_SCAN=true, ALDIMI_WAIT_FOR_SCAN=true, ALDIMI_SCAN_DNI=100, ALDIMI_SCAN_LAB=100 (TODAS LAS IMÁGENES)" -ForegroundColor Cyan

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
$psExe = Join-Path $PSHOME "powershell.exe"
$backendLog = Join-Path $root "backend\backend.log"

$backendCommand = "& '$activate'; Set-Location -LiteralPath '$root'; & '$venvPython' -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 2>&1 | Tee-Object -FilePath '$backendLog'"
$staticCommand  = "& '$activate'; Set-Location -LiteralPath '$root'; & '$venvPython' -m http.server $staticPort"

# Liberar puerto 8000 si hay algún listener huérfano.
Write-Host "Liberando puerto 8000 si está ocupado..." -ForegroundColor Cyan
try {
    Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Deteniendo proceso con PID=$($_.OwningProcess) que escucha en 8000" -ForegroundColor Yellow
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "No se pudo liberar el puerto 8000 automáticamente: $_" -ForegroundColor Yellow
}

Write-Host "Iniciando backend (uvicorn) en nueva ventana de PowerShell..."
Write-Host "El autoscan se ejecutará automáticamente al iniciar el servidor FastAPI (evento 'startup')." -ForegroundColor Cyan
Start-Process -FilePath $psExe -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-NoExit","-Command",$backendCommand -WorkingDirectory $root -WindowStyle Normal

Write-Host "Iniciando servidor estático en puerto $staticPort en nueva ventana..."
Start-Process -FilePath $psExe -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-NoExit","-Command",$staticCommand -WorkingDirectory $root -WindowStyle Normal

# Esperar a que el backend responda
$backendUrl = "http://127.0.0.1:8000"
Write-Host "Comprobando conectividad con el backend en $backendUrl ..."
$maxRetries = 60
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
    Write-Host "También revisa el archivo de logs: $backendLog" -ForegroundColor Yellow
    $listener = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Host "Hay un listener en el puerto 8000, pero el backend no responde correctamente." -ForegroundColor Yellow
    } else {
        Write-Host "No hay ningún proceso escuchando en el puerto 8000. El backend probablemente falló al arrancar." -ForegroundColor Yellow
    }
} else {
    Write-Host "Backend disponible. Abriendo frontend..." -ForegroundColor Green
}

# Abrir la página principal de inicio de sesión solo si el backend respondió
$indexUrl = "http://localhost:$staticPort/chatbot.html"
if ($ok) {
    Write-Host "Intentando abrir $indexUrl en el navegador predeterminado..."
    try {
        $proc = Start-Process -FilePath $indexUrl -ErrorAction Stop
        if ($proc) {
            Write-Host "Navegador iniciado con Start-Process (proceso creado)." -ForegroundColor Green
        } else {
            Write-Host "Start-Process no devolvió un objeto; intentando método alternativo..." -ForegroundColor Yellow
            Start-Process -FilePath "cmd.exe" -ArgumentList "/c","start","$indexUrl" -ErrorAction Stop
            Write-Host "Navegador abierto con 'cmd /c start'." -ForegroundColor Green
        }
    } catch {
        Write-Host "Start-Process falló, intentando 'cmd /c start'..." -ForegroundColor Yellow
        try {
            Start-Process -FilePath "cmd.exe" -ArgumentList "/c","start","$indexUrl" -ErrorAction Stop
            Write-Host "Navegador abierto con 'cmd /c start'." -ForegroundColor Green
        } catch {
            Write-Host "No se pudo abrir el navegador automáticamente. Abre manualmente:" -ForegroundColor Yellow
            Write-Host $indexUrl -ForegroundColor Cyan
        }
    }
    Write-Host "Listo. El backend está disponible." -ForegroundColor Cyan
} else {
    Write-Host "No se abrirá el frontend porque el backend no respondió." -ForegroundColor Yellow
    Write-Host "Revisa la ventana de PowerShell donde se inició uvicorn para encontrar el error y vuelve a ejecutar el script." -ForegroundColor Yellow
}
