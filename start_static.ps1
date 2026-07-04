$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    Write-Host "Usando Python del entorno virtual: $venvPython"
    & $venvPython -m http.server 5500
} else {
    Write-Host "Advertencia: no se encontró .venv\Scripts\python.exe. Se usará python del entorno." -ForegroundColor Yellow
    python -m http.server 5500
}
