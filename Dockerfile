# Imagen de producción de LecturaFácil.
#
# Uso:
#   docker build -t lecturafacil .
#   docker run --rm -p 8000:8000 --env-file .env lecturafacil
#
# Para App Service NO hace falta esta imagen (el despliegue por ZIP es más
# simple: no requiere un registro de contenedores). Se usa para ejecutar la
# app igual que en producción en cualquier máquina o servidor.

FROM python:3.12-slim

# Sin bytecode y salida sin buffer: los logs llegan al instante.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Primero las dependencias: así la capa se reutiliza si solo cambia el código.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Usuario sin privilegios (buena práctica, evita avisos de gunicorn).
RUN useradd --create-home --shell /usr/sbin/nologin lectura
USER lectura

EXPOSE 8000

# Comprobación de salud contra el endpoint /health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"]

# 1 worker: el plan gratuito de Azure tiene una sola vCPU.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "1", "-k", "uvicorn.workers.UvicornWorker", "app.main:app"]