"""Endpoint de salud para sondeos externos y monitorización.

Cloudflare Tunnel, App Service y varios balanceadores consultan ``/health``.
Devuelve el estado de la aplicación y qué servicios están operativos, **sin**
revelar ningún secreto (solo indicadores de sí/no).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import ContainerDep

router = APIRouter(tags=["health"])

SpeechMode = Literal["browser", "azure", "unavailable"]


class ServiceStatus(BaseModel):
    """Disponibilidad de cada servicio.

    Attributes:
        ocr: Si el servicio de lectura de imágenes está configurado.
        storage: Si el almacenamiento está configurado.
        speech: Motor de voz en uso (``browser``, ``azure`` o ``unavailable``).
        translation: Si hay diccionario o modelo de traducción disponible.
        demo_mode: Si la aplicación está en modo demostración.
    """

    ocr: bool
    storage: bool
    speech: SpeechMode
    translation: bool
    demo_mode: bool


class HealthResponse(BaseModel):
    """Respuesta del sondeo de salud.

    Attributes:
        status: ``ok`` si la aplicación responde.
        app: Nombre de la aplicación.
        version: Versión desplegada.
        environment: Entorno de ejecución.
        services: Estado de los servicios.
    """

    status: Literal["ok"] = "ok"
    app: str
    version: str
    environment: str
    services: ServiceStatus


@router.get("/health", response_model=HealthResponse, summary="Estado de la aplicación")
@router.get(
    "/api/health",
    response_model=HealthResponse,
    include_in_schema=False,
    summary="Estado de la aplicación (con prefijo /api)",
)
async def health(container: ContainerDep) -> HealthResponse:
    """Comprueba que la aplicación responde e informa de sus servicios.

    Args:
        container: Contenedor de servicios.

    Returns:
        Estado de la aplicación y de sus dependencias.
    """
    settings = container.settings
    speech: SpeechMode = (
        "unavailable"
        if settings.demo_mode
        else ("browser" if settings.speech_backend == "browser" else "azure")
    )
    return HealthResponse(
        app=settings.app_name,
        version="1.0.0",
        environment=settings.environment,
        services=ServiceStatus(
            ocr=settings.ocr_configured,
            storage=settings.storage_configured,
            speech=speech,
            translation=True,
            demo_mode=settings.demo_mode,
        ),
    )
