# Publícalo con un túnel HTTPS gratuito (Cloudflare).
#
# Útil cuando App Service no tiene cuota en la suscripción (Azure for Students
# solo permite 0 planes de App Service). Cuesta 0 € y sirve los servicios
# reales de Azure (OCR, Blob Storage y traducción).
#
# Uso:
#   1) Instalar cloudflared (una vez)
#      winget install --id Cloudflare.cloudflared -e
#
#   2) Arrancar la aplicación
#      .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
#
#   3) En otra terminal, exponerla
#      cloudflared tunnel --url http://127.0.0.1:8000
#
#      -> imprime algo como https://algo-aleatorio.trycloudflare.com
#
# Consideraciones:
#   - La URL cambia en cada ejecución.
#   - El túnel es temporal: se cierra al cerrar la terminal o el proceso.
#   - El ordenador debe seguir encendido con la app corriendo.
#   - HTTPS automático: es lo que permite usar el micrófono en el móvil.

$ErrorActionPreference = "Stop"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "cloudflared no está instalado." -ForegroundColor Yellow
    Write-Host "Instálalo con:  winget install --id Cloudflare.cloudflared -e" -ForegroundColor Yellow
    Write-Host "y vuelve a ejecutar este script." -ForegroundColor Yellow
    exit 1
}

$url = "http://127.0.0.1:8000/health"

try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
    Write-Host "La aplicación responde en $url (HTTP $($response.StatusCode))" -ForegroundColor Green
    Write-Host $response.Content
} catch {
    Write-Host "No hay ninguna aplicación escuchando en $url" -ForegroundColor Red
    Write-Host "Arranca primero la app en otra terminal:" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Para exponerla por Internet, deja esto corriendo:" -ForegroundColor Cyan
Write-Host "  cloudflared tunnel --url http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Copia la URL https://...trycloudflare.com que aparezca y ábrela" -ForegroundColor Cyan
Write-Host "en el móvil o en el portátil." -ForegroundColor Cyan