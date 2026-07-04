$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath (Join-Path $root 'backend')
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    Write-Host "Usando Python del entorno virtual: $venvPython"
    & $venvPython -m uvicorn main:app --reload --port 8000
} else {
    Write-Host "Advertencia: no se encontró .venv\Scripts\python.exe. Se usará python del entorno." -ForegroundColor Yellow
    python -m uvicorn main:app --reload --port 8000
}
