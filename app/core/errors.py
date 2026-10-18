"""Jerarquía de errores de dominio y traducción a respuestas HTTP.

Los errores de dominio llevan siempre una ``message_key`` traducible para que
el frontend muestre un mensaje en el idioma del niño, nunca un texto técnico.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.i18n import Translator, normalize_language

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Error base de la aplicación.

    Args:
        message_key: Clave traducible del mensaje.
        status_code: Código HTTP asociado.
        code: Identificador estable del error para el cliente.
        detail: Contexto adicional (nunca contiene datos sensibles).
    """

    def __init__(
        self,
        message_key: str = "error.generic",
        status_code: int = 400,
        code: str = "app_error",
        **detail: Any,
    ) -> None:
        super().__init__(message_key)
        self.message_key = message_key
        self.status_code = status_code
        self.code = code
        self.detail: dict[str, Any] = detail

    def message(self, language: str | None) -> str:
        """Devuelve el mensaje ya traducido.

        Args:
            language: Idioma solicitado.

        Returns:
            Mensaje en el idioma indicado.
        """
        return Translator(language).t(self.message_key, **self.detail)


class ValidationError(AppError):
    """Entrada de usuario inválida."""


class NotFoundError(AppError):
    """Recurso inexistente."""


class ConfigurationError(AppError):
    """Falta configuración de un servicio de Azure."""


class ServiceError(AppError):
    """Un servicio externo falló o respondió de forma inesperada."""


def _request_language(request: Request) -> str:
    """Resuelve el idioma de la petición (cookie, query o cabecera).

    Args:
        request: Petición HTTP entrante.

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


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convierte un :class:`AppError` en una respuesta JSON coherente.

    Args:
        request: Petición HTTP entrante.
        exc: Error de dominio lanzado.

    Returns:
        Respuesta JSON con el código estable y el mensaje traducido.
    """
    if not isinstance(exc, AppError):
        raise exc
    language = _request_language(request)
    logger.warning(
        "Error de aplicación %s: %s", exc.code, exc.message_key, exc_info=False
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message(language),
                "message_key": exc.message_key,
                "detail": exc.detail,
            }
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Respuesta genérica para errores no controlados.

    Args:
        request: Petición HTTP entrante.
        exc: Excepción inesperada.

    Returns:
        Respuesta JSON 500 sin detalles internos.
    """
    logger.exception("Error no controlado en %s", request.url.path)
    language = _request_language(request)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": Translator(language).t("error.generic"),
                "message_key": "error.generic",
                "detail": {},
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers JSON de la aplicación.

    Args:
        app: Aplicación FastAPI.
    """

    handlers: dict[Any, Callable[[Request, Exception], Awaitable[JSONResponse]]] = {
        AppError: app_error_handler,
        Exception: unhandled_error_handler,
    }
    for exception_class, handler in handlers.items():
        app.add_exception_handler(exception_class, handler)
