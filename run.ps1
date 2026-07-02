<#
run.ps1
PowerShell helper to prepare environment and run the local API + static server.

Usage: Open PowerShell in the project folder and run:
    .\run.ps1

This script will:
- Create a virtual environment in `.venv` (if missing)
- Install `requirements.txt` into the venv
- Check Tesseract binary at the default path
- Launch the backend FastAPI server in a new window
- Launch the frontend HTTP server in a new window
- Open the browser on `index.html`
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "ALDIMI: Preparando entorno..." -ForegroundColor Cyan

$scriptRoot = $PSScriptRoot
$venvPath = Join-Path $scriptRoot '.venv'
$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
$pythonCmd = 'python'

if (-not (Test-Path $venvPath)) {
    Write-Host "Creando virtualenv en: $venvPath" -ForegroundColor Yellow
    & $pythonCmd -m venv $venvPath
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "No se encontró el intérprete en .venv. Usando el intérprete del sistema." -ForegroundColor Yellow
    $pythonExe = $pythonCmd
}

Write-Host "Actualizando pip e instalando dependencias..." -ForegroundColor Cyan
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $scriptRoot 'requirements.txt')

$tessPath = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
if (Test-Path $tessPath) {
    Write-Host "Tesseract encontrado en: $tessPath" -ForegroundColor Green
    & $tessPath --version
} else {
    Write-Host "Advertencia: no se encontró Tesseract en: $tessPath" -ForegroundColor Yellow
    Write-Host "Instale Tesseract o coloque el ejecutable en esa ruta para que funcione el OCR local." -ForegroundColor Yellow
}

$apiPort = 8000
$webPort = 5500
$uiUrl = "http://127.0.0.1:$webPort/index.html"

# Determinar módulo uvicorn a ejecutar (preferir main_local.py para dev, luego main.py, luego ocr.py)
$uvicornModule = 'ocr:app'
if (Test-Path (Join-Path $scriptRoot 'main_local.py')) { $uvicornModule = 'main_local:app' }
elseif (Test-Path (Join-Path $scriptRoot 'main.py')) { $uvicornModule = 'main:app' }
elseif (Test-Path (Join-Path $scriptRoot 'ocr.py')) { $uvicornModule = 'ocr:app' }

Write-Host "Iniciando backend FastAPI ($uvicornModule)..." -ForegroundColor Cyan
Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'uvicorn', $uvicornModule, '--reload', '--host', '127.0.0.1', '--port', $apiPort) -WorkingDirectory $scriptRoot

Write-Host "Iniciando servidor estático para el frontend..." -ForegroundColor Cyan
Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'http.server', $webPort) -WorkingDirectory $scriptRoot

Start-Sleep -Seconds 5

Write-Host "Verificando conexión con el backend..." -ForegroundColor Cyan
$healthOk = $false
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$apiPort/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) { $healthOk = $true }
} catch {
    Write-Host "Advertencia: no se pudo conectar al backend en http://127.0.0.1:$apiPort" -ForegroundColor Yellow
}

Write-Host "Abriendo navegador en: $uiUrl" -ForegroundColor Cyan
Start-Process $uiUrl

if ($healthOk) {
    Write-Host "Backend disponible en http://127.0.0.1:$apiPort" -ForegroundColor Green
} else {
    Write-Host "El frontend abrió, pero el backend no respondió todavía." -ForegroundColor Yellow
    Write-Host "Revise la ventana de PowerShell del backend para ver errores." -ForegroundColor Yellow
}

Write-Host "Si cerró la ventana del backend, el chatbot y OCR dejarán de funcionar." -ForegroundColor Yellow
