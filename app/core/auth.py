"""Autenticación hacia los servicios de Azure AI (Vision, Document
Intelligence y Speech).

En Azure se usa la Managed Identity del App Service mediante
``DefaultAzureCredential``; en desarrollo local es posible usar una clave
estática de los servicios.
"""

from __future__ import annotations

import logging

from azure.identity.aio import DefaultAzureCredential

from app.core.config import AZURE_COGNITIVE_SCOPE, Settings
from app.core.errors import ConfigurationError

logger = logging.getLogger(__name__)


class CognitiveAuth:
    """Proveedor de cabeceras de autenticación para Azure AI.

    Args:
        credential: Credencial asíncrona de Entra ID (puede ser ``None`` si no
            hay identidad disponible).
        subscription_key: Clave estática opcional para desarrollo local.

    Raises:
        ConfigurationError: Si no hay ni credencial ni clave disponible.
    """

    def __init__(
        self,
        credential: DefaultAzureCredential | None = None,
        subscription_key: str | None = None,
    ) -> None:
        self._credential = credential
        self._subscription_key = subscription_key

    async def headers(self) -> dict[str, str]:
        """Devuelve la cabecera de autorización para una llamada a Azure AI.

        Returns:
            Cabeceras con ``Authorization: Bearer`` o
            ``Ocp-Apim-Subscription-Key``.

        Raises:
            ConfigurationError: Si no hay credenciales configuradas.
        """
        if self._credential is not None:
            token = await self._credential.get_token(AZURE_COGNITIVE_SCOPE)
            return {"Authorization": f"Bearer {token.token}"}
        if self._subscription_key:
            return {"Ocp-Apim-Subscription-Key": self._subscription_key}
        raise ConfigurationError(
            "error.not_configured",
            status_code=503,
            code="azure_identity_missing",
            service="DefaultAzureCredential",
        )


async def create_credential(settings: Settings) -> DefaultAzureCredential | None:
    """Crea la credencial de Entra ID si es posible en este entorno.

    Args:
        settings: Ajustes de la aplicación.

    Returns:
        La credencial creada o ``None`` si no hay identidad (por ejemplo,
        durante las pruebas).
    """
    try:
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)
    except Exception:  # pragma: no cover - depende del entorno de ejecución
        logger.warning(
            "No se ha podido crear DefaultAzureCredential; "
            "se usarán claves estáticas si están configuradas."
        )
        return None


async def close_credential(credential: object | None) -> None:
    """Cierra la credencial de Entra ID si procede.

    Args:
        credential: Credencial creada por :func:`create_credential`.
    """
    close = getattr(credential, "close", None)
    if close is None:
        return
    try:
        result = close()
        if hasattr(result, "__await__"):
            await result
    except Exception:  # pragma: no cover - cierre best effort
        logger.debug("No se pudo cerrar la credencial de Azure", exc_info=True)
