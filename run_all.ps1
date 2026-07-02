<#
run_all.ps1
PowerShell helper to prepare environment and run the local API + static server.

Usage: Open PowerShell in the project folder and run:
    .\run_all.ps1

This script will:
- Create a virtual environment in `.venv` (if missing)
- Install `requirements.txt` into the venv
- Check Tesseract binary at the default path
- Launch `uvicorn ocr:app` in a new PowerShell window
- Open the browser at http://127.0.0.1:8000/
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "ALDIMI: Preparando entorno..." -ForegroundColor Cyan

$venv = Join-Path -Path $PSScriptRoot -ChildPath ".venv"
$python = "python"

if (-not (Test-Path $venv)) {
    Write-Host "Creando virtualenv en $venv" -ForegroundColor Yellow
    & $python -m venv $venv
}

$pyExe = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    Write-Host "No se encontró .venv. Usando el intérprete del sistema." -ForegroundColor Yellow
    $pyExe = $python
}

Write-Host "Actualizando pip e instalando dependencias..." -ForegroundColor Cyan
& $pyExe -m pip install --upgrade pip > $null
& $pyExe -m pip install -r requirements.txt

# Verificar Tesseract
$tessPath = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
if (Test-Path $tessPath) {
    Write-Host "Tesseract encontrado en: $tessPath" -ForegroundColor Green
    & $tessPath --version
} else {
    Write-Host "Advertencia: no se encontró Tesseract en $tessPath" -ForegroundColor Yellow
    Write-Host "Si lo tiene instalado en otra ruta, edite 'aldimi_web_local.py' o mueva tesseract al path esperado." -ForegroundColor Yellow
}

# Puerto y comando
$apiPort = 8000
# El módulo principal es ocr.py para la versión local con Tesseract.
$uvicornCmd = "& '$pyExe' -m uvicorn ocr:app --reload --host 127.0.0.1 --port $apiPort"

Write-Host "Iniciando API en puerto $apiPort (nueva ventana)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit","-Command","`$env:ALDIMI_ENV='local'; Write-Host 'API: ejecutando uvicorn...'; & '$pyExe' -m uvicorn ocr:app --reload --host 127.0.0.1 --port $apiPort"

Start-Sleep -Seconds 1
$url = "http://127.0.0.1:$apiPort/"
Write-Host "Abriendo navegador en: $url" -ForegroundColor Cyan
Start-Process $url

Write-Host "Listo. Revise la ventana de PowerShell abierta para ver logs de la API." -ForegroundColor Green
