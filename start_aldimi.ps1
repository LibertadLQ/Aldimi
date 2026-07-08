# start_aldimi.ps1 - Script para iniciar ALDIMI backend y frontend

param([switch]$NoBrowser)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "ALDIMI - Sistema de Alertas Clinicas" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $root

# Paso 1: Directorios
Write-Host "[1/5] Preparando directorios..." -ForegroundColor White
$aldbPath = Join-Path $root "ALDIMI_DB"
New-Item -ItemType Directory -Path $aldbPath, (Join-Path $root "DNI_ALDIMI"), (Join-Path $root "LAB_ALDIMI") -Force | Out-Null
$env:ALDIMI_DB_PATH = $aldbPath
$env:PYTHONUTF8 = "1"
Write-Host "     OK" -ForegroundColor Green

# Paso 2: Python
Write-Host "[2/5] Verificando Python..." -ForegroundColor White
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "     ERROR: Python no encontrado en PATH" -ForegroundColor Red
    exit 1
}
Write-Host "     OK" -ForegroundColor Green

# Paso 3: Virtual Environment
Write-Host "[3/5] Configurando entorno virtual..." -ForegroundColor White
$venvPath = Join-Path $root ".venv"
if (-not (Test-Path (Join-Path $venvPath "Scripts\Activate.ps1"))) {
    python -m venv .venv
}
& (Join-Path $venvPath "Scripts\Activate.ps1")
python -m pip install --upgrade pip wheel -q 2>&1 | Out-Null
Write-Host "     OK" -ForegroundColor Green

# Paso 4: Dependencias
Write-Host "[4/5] Instalando dependencias..." -ForegroundColor White
$reqFile = Join-Path $root "backend\requirements.txt"
if (Test-Path $reqFile) {
    python -m pip install -r $reqFile -q 2>&1 | Out-Null
    Write-Host "     OK" -ForegroundColor Green
} else {
    Write-Host "     ERROR: backend/requirements.txt no encontrado" -ForegroundColor Red
    exit 1
}

# Paso 5: Servicios
Write-Host "[5/5] Iniciando servicios..." -ForegroundColor White

$venvPython = Join-Path $venvPath "Scripts\python.exe"
$psExe = Join-Path $PSHOME "powershell.exe"

# Liberar puerto 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

# Comando backend
$backendCmd = @"
`$ErrorActionPreference = 'Continue'
& '$( Join-Path $venvPath "Scripts\Activate.ps1" )'
Set-Location '$root'
`$env:ALDIMI_DB_PATH = '$aldbPath'
`$env:ALDIMI_AUTO_SCAN = 'true'
`$env:ALDIMI_WAIT_FOR_SCAN = 'false'
`$env:ALDIMI_SCAN_DNI = '100'
`$env:ALDIMI_SCAN_LAB = '100'
Write-Host 'Backend iniciado en http://127.0.0.1:8000' -ForegroundColor Cyan
& '$venvPython' -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload 2>&1
"@

# Comando frontend
$staticCmd = @"
`$ErrorActionPreference = 'Continue'
& '$( Join-Path $venvPath "Scripts\Activate.ps1" )'
Set-Location '$root'
Write-Host 'Servidor estatico iniciado en http://127.0.0.1:5500' -ForegroundColor Cyan
& '$venvPython' -m http.server 5500
"@

Start-Process -FilePath $psExe -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-NoExit","-Command",$backendCmd -WorkingDirectory $root
Start-Sleep -Seconds 2
Start-Process -FilePath $psExe -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-NoExit","-Command",$staticCmd -WorkingDirectory $root
Start-Sleep -Seconds 1

Write-Host "     OK" -ForegroundColor Green

# Verificar backend
Write-Host ""
Write-Host "Esperando respuesta del backend..." -ForegroundColor Gray

$maxRetries = 120
$retry = 0
while ($retry -lt $maxRetries) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8000" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
        Write-Host "Backend disponible!" -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 1
        $retry++
    }
}

Write-Host ""
if ($retry -ge $maxRetries) {
    Write-Host "ERROR: Backend no respondio despues de $maxRetries segundos" -ForegroundColor Red
    Write-Host "Verifica la ventana de PowerShell donde se inicio uvicorn para ver errores" -ForegroundColor Yellow
    exit 1
}

Write-Host "=====================================================" -ForegroundColor Green
Write-Host "ALDIMI INICIADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Frontend: http://localhost:5500/chatbot.html" -ForegroundColor Cyan
Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

if (-not $NoBrowser) {
    try {
        Start-Process "http://localhost:5500/chatbot.html"
    } catch {
        Write-Host "No se pudo abrir navegador automaticamente" -ForegroundColor Yellow
    }
}

Write-Host "Presiona Ctrl+C en las ventanas de PowerShell para detener" -ForegroundColor Gray
Write-Host ""
