"""Configuración de las plantillas Jinja2.

La ruta se calcula respecto al propio archivo del paquete, nunca respecto al
directorio de trabajo.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)
