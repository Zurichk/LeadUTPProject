"""Fábrica de la aplicación FastAPI.

Arranque:
    ``uvicorn app.main:app --reload`` (desde la raíz del repositorio).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import ALL_ROUTERS
from app.container import ServiceContainer, build_container, shutdown_container
from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

ContainerBuilder = Callable[[Settings], Awaitable[ServiceContainer]]

DESCRIPTION = """
Asistente infantil de lectura en castellano y valenciano.

Sube una foto de la ficha de lectura, obtén las palabras detectadas con OCR,
escucha su pronunciación (Text-to-Speech) y comprueba la pronunciación de la
niña (Speech-to-Text).
"""


def create_app(
    settings: Settings | None = None,
    container_builder: ContainerBuilder | None = None,
) -> FastAPI:
    """Crea y configura la aplicación FastAPI.

    Args:
        settings: Ajustes opcionales (por defecto se leen del entorno).
        container_builder: Fábrica del contenedor de servicios; se sustituye en
            las pruebas para inyectar dobles.

    Returns:
        Aplicación lista para servir.
    """
    app_settings = settings or Settings()
    build_services = container_builder or build_container
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Construye los servicios al arrancar y los libera al parar.

        Args:
            app: Aplicación FastAPI.

        Yields:
            ``None`` mientras la aplicación está activa.
        """
        container = await build_services(app_settings)
        app.state.container = container
        logger.info(
            "%s iniciado en modo %s (OCR: %s)",
            app_settings.app_name,
            app_settings.environment,
            app_settings.ocr_provider,
        )
        try:
            yield
        finally:
            await shutdown_container(container)
            app.state.container = None

    app = FastAPI(
        title=app_settings.app_name,
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    register_exception_handlers(app)
    for router in ALL_ROUTERS:
        app.include_router(router)
    app.mount(
        "/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static"
    )
    return app


app = create_app()
