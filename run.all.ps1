<#
Compatibility wrapper: run.all.ps1 -> run_all.ps1
Si el usuario escribe por error `run.all.ps1`, este wrapper invocará
el script correcto `run_all.ps1` en la misma carpeta.
#>

Set-StrictMode -Version Latest
$script = Join-Path $PSScriptRoot 'run_all.ps1'
if (Test-Path $script) {
    Write-Host "Invocando $script..." -ForegroundColor Cyan
    & $script
} else {
    Write-Host "No se encontró 'run_all.ps1' en: $PSScriptRoot" -ForegroundColor Red
    Write-Host "Archivos en carpeta:" -ForegroundColor Yellow
    Get-ChildItem -Path $PSScriptRoot -File | ForEach-Object { Write-Host $_.Name }
    exit 1
}
