# Empaqueta la aplicación para desplegarla en Azure App Service (Linux).
#
# Crea dist.zip con lo mínimo necesario en el servidor:
#   - app/            (código, plantillas y estáticos)
#   - requirements.txt (obligatorio: App Service lo necesita en la raíz)
#
# NO incluye .env (tiene secretos), tests, documentación ni el entorno virtual.
#
# Uso (PowerShell):
#   pwsh scripts/empaquetar.ps1
#   pwsh scripts/empaquetar.ps1 -Salida dist.zip

param(
    [string]$Salida = "dist.zip"
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$staging = Join-Path $raiz "dist"

Write-Host ">> Empaquetando LecturaFácil..." -ForegroundColor Cyan

# 1. Limpiar la carpeta de preparación
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
if (Test-Path (Join-Path $raiz $Salida)) { Remove-Item (Join-Path $raiz $Salida) -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

# 2. Copiar solo lo necesario
Copy-Item (Join-Path $raiz "app") -Destination $staging -Recurse -Force
Copy-Item (Join-Path $raiz "requirements.txt") -Destination $staging -Force

# 2b. Quitar la caché de Python: son .pyc de la versión local (3.14) y el
#     App Service usa 3.12. Python los ignoraría, pero solo engordan el ZIP.
Get-ChildItem -Path $staging -Recurse -Directory -Filter "__pycache__" -Force |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $staging -Recurse -File -Include "*.pyc", "*.pyo" -Force |
    Remove-Item -Force -ErrorAction SilentlyContinue

# 3. Comprobar que no se cuela ningún secreto
$secretos = Get-ChildItem -Path $staging -Recurse -Force -Include ".env", ".env.*" -ErrorAction SilentlyContinue
if ($secretos) {
    Write-Host "ERROR: hay ficheros de entorno en el paquete: $($secretos.Name)" -ForegroundColor Red
    exit 1
}

# 4. Crear el ZIP
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath (Join-Path $raiz $Salida) -Force

# 5. Mostrar un resumen de lo que contiene
$zip = Get-Item (Join-Path $raiz $Salida)
$archivos = (Get-ChildItem -Path $staging -Recurse -File).Count
Write-Host ""
Write-Host "ZIP creado: $($zip.FullName)" -ForegroundColor Green
Write-Host ("  Tamaño  : {0:N1} KB" -f ($zip.Length / 1KB))
Write-Host "  Archivos: $archivos"

Write-Host ""
Write-Host "Contenido (primer nivel):" -ForegroundColor Cyan
Get-ChildItem -Path $staging | ForEach-Object { Write-Host "  $($_.Name)" }

$hayRequirements = Test-Path (Join-Path $staging "requirements.txt")
$hayMain = Test-Path (Join-Path $staging "app\main.py")
Write-Host ""
if ($hayRequirements -and $hayMain) {
    Write-Host "Comprobación OK: requirements.txt y app/main.py están en la raíz." -ForegroundColor Green
} else {
    Write-Host "ERROR: falta requirements.txt o app/main.py en la raíz." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Siguiente paso: sube '$Salida' a Cloud Shell y ejecuta" -ForegroundColor Cyan
Write-Host "  DEPLOY_ZIP=$Salida bash setup-cloud-shell.sh"