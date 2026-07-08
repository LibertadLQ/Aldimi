# run.ps1 - Script principal de ALDIMI
# Ejecutar: .\run.ps1
# Este script inicia el backend FastAPI y servidor estático

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "ALDIMI - Sistema de Alertas Clinicas" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

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

Write-Host "Rutas de datos:" -ForegroundColor Cyan
Write-Host "  ALDIMI_DB=$aldbPath" -ForegroundColor Gray
Write-Host "  DNI_ALDIMI=$dniPath" -ForegroundColor Gray
Write-Host "  LAB_ALDIMI=$labPath" -ForegroundColor Gray

# El backend de producción usa el código de backend/, no el notebook Colab.
$env:PYTHONUTF8 = "1"
Write-Host "Variables de entorno:" -ForegroundColor Cyan
Write-Host "  PYTHONUTF8=1" -ForegroundColor Gray

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
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} else {
    Write-Host "ERROR: Python no está en PATH. Instala Python 3.8+ y reintenta." -ForegroundColor Red
    exit 1
}

$venvPath = Join-Path $root ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creando entorno virtual .venv..."
    & $pythonCmd -m venv .venv
}

# Activate venv in this session
$activate = Join-Path $venvPath "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Write-Host "ERROR: No se encontró el script de activación: $activate" -ForegroundColor Red
    exit 1
}

Write-Host "Activando .venv..."
& $activate

Write-Host "Actualizando pip y wheel..."
python -m pip install --upgrade pip wheel

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

 $backendErrLog = Join-Path $root "backend\backend.err.log"

 # Asegurar que el backend arranque desde el Python del entorno virtual.
 $backendArgs = @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000")
 $staticArgs  = @("-m", "http.server", "$staticPort")

 # Asegurar que exista el archivo de log y el log de errores
 $logDir = Split-Path -Parent $backendLog
 if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
 if (-not (Test-Path $backendLog)) { New-Item -ItemType File -Path $backendLog -Force | Out-Null }
 if (-not (Test-Path $backendErrLog)) { New-Item -ItemType File -Path $backendErrLog -Force | Out-Null }

# Liberar puerto 8000 si hay algún listener huérfano.
Write-Host "Liberando puerto 8000 si está ocupado..." -ForegroundColor Cyan
try {
    $connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $connections | ForEach-Object {
            Write-Host "Deteniendo proceso con PID=$($_.OwningProcess) que escucha en 8000" -ForegroundColor Yellow
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    } else {
        Write-Host "Puerto 8000 disponible." -ForegroundColor Green
    }
} catch {
    Write-Host "No se pudo liberar el puerto 8000 automáticamente: $_" -ForegroundColor Yellow
}

Write-Host "Iniciando backend (uvicorn) en nueva ventana de PowerShell..." -ForegroundColor Cyan
Write-Host "El autoscan se ejecutará automáticamente al iniciar el servidor FastAPI (evento 'startup')." -ForegroundColor Cyan
Write-Host "Logs del backend se guardarán en: $backendLog" -ForegroundColor Gray

 # Construir comando que se ejecutará en la nueva ventana de PowerShell y que además hace tee al log
 $backendCommand = "Set-Location -LiteralPath '$root'; `$env:ALDIMI_AUTO_SCAN='true'; `$env:ALDIMI_WAIT_FOR_SCAN='false'; `$env:ALDIMI_SCAN_DNI='100'; `$env:ALDIMI_SCAN_LAB='100'; & '$venvPython' -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 2>&1 | Tee-Object -FilePath '$backendLog'"

 $backendProcess = Start-Process -FilePath $psExe -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-NoExit","-Command",$backendCommand -WorkingDirectory $root -WindowStyle Normal -PassThru
 if ($backendProcess -ne $null) {
     Write-Host "Backend iniciado con PID=$($backendProcess.Id)" -ForegroundColor Green
 } else {
     Write-Host "ERROR: No se pudo iniciar el proceso del backend." -ForegroundColor Red
 }
Start-Sleep -Seconds 2

Write-Host "Iniciando servidor estático en puerto $staticPort en nueva ventana..."
Start-Process -FilePath $venvPython -ArgumentList $staticArgs -WorkingDirectory $root -WindowStyle Normal -PassThru

# Esperar a que el backend responda
$backendUrl = "http://127.0.0.1:8000"
Write-Host "Comprobando conectividad con el backend en $backendUrl ..." -ForegroundColor Cyan
$maxRetries = 180
$retry = 0
$ok = $false
while ($retry -lt $maxRetries) {
    try {
        $resp = Invoke-WebRequest -Uri $backendUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        Write-Host "✅ Backend respondió (HTTP $($resp.StatusCode)). Continuando..." -ForegroundColor Green
        $ok = $true
        break
    } catch {
        if ($retry % 10 -eq 0 -and $retry -gt 0) {
            Write-Host "⏳ Aún esperando backend... ($retry/$maxRetries segundos)" -ForegroundColor Gray
        }
        Start-Sleep -Seconds 1
        $retry++
    }
}
if (-not $ok) {
    Write-Host "❌ ERROR: No se detectó el backend en $backendUrl después de $maxRetries segundos." -ForegroundColor Red
    Write-Host "Posibles causas:" -ForegroundColor Yellow
    Write-Host "  1. Error de importación en backend/main.py - revisa la ventana de uvicorn" -ForegroundColor Yellow
    Write-Host "  2. Falta alguna dependencia - ejecuta: pip install -r backend/requirements.txt" -ForegroundColor Yellow
    Write-Host "  3. Puerto 8000 no se liberó correctamente" -ForegroundColor Yellow
    Write-Host "Soluciones:" -ForegroundColor Cyan
    Write-Host "  • Revisa la ventana de PowerShell donde se inició uvicorn para ver el error exacto" -ForegroundColor Cyan
    Write-Host "  • Archivo de logs: $backendLog" -ForegroundColor Cyan
    Write-Host "  • Intenta: Stop-Process -Name python -Force; .\run.ps1" -ForegroundColor Cyan
    $listener = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Host "⚠️  Hay un listener en el puerto 8000, pero el backend no responde correctamente." -ForegroundColor Yellow
    } else {
        Write-Host "⚠️  No hay ningún proceso escuchando en el puerto 8000. El backend falló al arrancar." -ForegroundColor Yellow
    }
} else {
    Write-Host "✅ Backend disponible. Abriendo frontend..." -ForegroundColor Green
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
