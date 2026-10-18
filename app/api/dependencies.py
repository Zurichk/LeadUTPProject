"""Dependencias compartidas por los routers.

El contenedor de servicios se construye en el arranque de la aplicación y se
expone a los routers por inyección de dependencias, de modo que ninguna ruta
instancia adaptadores de Azure.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.container import ServiceContainer
from app.core.errors import ServiceError
from app.core.i18n import normalize_language


def get_container(request: Request) -> ServiceContainer:
    """Devuelve el contenedor de servicios de la aplicación.

    Args:
        request: Petición HTTP en curso.

    Returns:
        Contenedor con los servicios ya inicializados.

    Raises:
        ServiceError: Si el contenedor aún no está disponible.
    """
    container: ServiceContainer | None = getattr(request.app.state, "container", None)
    if container is None:
        raise ServiceError("error.generic", status_code=503, code="container_not_ready")
    return container


def get_language(request: Request) -> str:
    """Resuelve el idioma de la petición.

    Prioridad: parámetro ``lang`` > cookie ``lang`` > cabecera
    ``Accept-Language``.

    Args:
        request: Petición HTTP en curso.

    Returns:
        Código de idioma normalizado.
    """
    query_language = request.query_params.get("lang")
    if query_language:
        return normalize_language(query_language)
    cookie_language = request.cookies.get("lang")
    if cookie_language:
        return normalize_language(cookie_language)
    return normalize_language(request.headers.get("accept-language"))


ContainerDep = Annotated[ServiceContainer, Depends(get_container)]
LanguageDep = Annotated[str, Depends(get_language)]
