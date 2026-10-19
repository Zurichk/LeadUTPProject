<#
.SYNOPSIS
    Valida la sintaxis de los archivos Bicep sin desplegar nada.

.DESCRIPTION
    Compila los .bicep a ARM JSON. No hace falta Azure ni suscripción: es una
    comprobación local de sintaxis, tipos y dependencias.

.EXAMPLE
    pwsh -File scripts/validar-bicep.ps1

.EXAMPLE
    pwsh -File scripts/validar-bicep.ps1 -BicepPath "C:\ruta\bicep.exe"
#>
[CmdletBinding()]
param(
    [Parameter()]
    [string]$BicepPath = "bicep"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$infra = Join-Path $root "infra"

if (-not (Get-Command $BicepPath -ErrorAction SilentlyContinue) -and
    -not (Test-Path $BicepPath)) {
    Write-Host "No encuentro Bicep CLI." -ForegroundColor Yellow
    Write-Host "Instálalo con una de estas opciones:" -ForegroundColor Yellow
    Write-Host "  winget install Bicep.Bicep" -ForegroundColor Yellow
    Write-Host "  o en Cloud Shell: az bicep install" -ForegroundColor Yellow
    exit 1
}

$fallos = 0

foreach ($archivo in @("main.bicep", "services.bicep", "probar-audio.bicep")) {
    $ruta = Join-Path $infra $archivo
    Write-Host "==> $archivo" -ForegroundColor Cyan

    $salida = & $BicepPath build $ruta --outfile (Join-Path $env:TEMP "bicep-check.json") 2>&1
    $codigo = $LASTEXITCODE

    if ($salida) {
        $salida | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
    }

    if ($codigo -eq 0 -and -not $salida) {
        Write-Host "    correcto, sin errores ni avisos" -ForegroundColor Green
    } elseif ($codigo -ne 0) {
        Write-Host "    FALLO al compilar" -ForegroundColor Red
        $fallos++
    }
}

Write-Host ""
if ($fallos -eq 0) {
    Write-Host "Todo correcto. Puedes desplegar con:" -ForegroundColor Green
    Write-Host "  az deployment sub create --location westeurope --template-file infra/main.bicep --parameters uniqueSuffix=<sfx>"
    exit 0
}

Write-Host "$fallos archivo(s) con errores." -ForegroundColor Red
exit 1