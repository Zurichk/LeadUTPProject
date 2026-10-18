"""Persistencia de imágenes de fichas y perfiles en Azure Blob Storage.

El adaptador usa la Managed Identity del App Service cuando se proporciona
``blob_service_url``; la cadena de conexión queda reservada para desarrollo
local.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from azure.core.exceptions import HttpResponseError, ResourceExistsError
from azure.storage.blob.aio import BlobServiceClient

from app.core.config import Settings
from app.core.errors import ConfigurationError, ServiceError

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
MAX_PROFILES = 20


class StoragePort(Protocol):
    """Contrato mínimo de almacenamiento de objetos."""

    async def upload_image(
        self,
        content: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> str:
        """Guarda la imagen de una ficha.

        Args:
            content: Bytes de la imagen.
            filename: Nombre original (se sanea).
            content_type: Tipo MIME de la imagen.

        Returns:
            Nombre del blob creado.
        """
        ...

    async def read_json(self, blob_name: str) -> dict[str, Any] | None:
        """Lee un blob JSON.

        Args:
            blob_name: Nombre del blob.

        Returns:
            Contenido JSON o ``None`` si el blob no existe.
        """
        ...

    async def write_json(self, blob_name: str, payload: dict[str, Any]) -> None:
        """Sobrescribe un blob JSON.

        Args:
            blob_name: Nombre del blob.
            payload: Objeto serializable a JSON.
        """
        ...


def sanitize_filename(filename: str) -> str:
    """Sanea el nombre de un archivo subido.

    Elimina cualquier componente de ruta y deja solo caracteres seguros.

    Args:
        filename: Nombre original recibido del cliente.

    Returns:
        Nombre seguro sin directorios ni caracteres especiales.
    """
    base = Path(filename or "ficha.jpg").name
    cleaned = _SAFE_NAME_RE.sub("-", base).strip("-.")
    return cleaned or "ficha.jpg"


def build_blob_name(filename: str, *, prefix: str = "fichas") -> str:
    """Genera un nombre único y seguro para el blob de una ficha.

    Args:
        filename: Nombre original de la imagen.
        prefix: Carpeta lógica dentro del contenedor.

    Returns:
        Ruta del blob, por ejemplo ``fichas/20240101-uuid-ficha.jpg``.
    """
    suffix = Path(sanitize_filename(filename)).suffix.lower() or ".jpg"
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}/{stamp}-{uuid.uuid4().hex[:8]}{suffix}"


class BlobStorageService:
    """Adaptador de Azure Blob Storage.

    Args:
        settings: Ajustes de la aplicación.
        credential: Credencial de Entra ID (Managed Identity) opcional.
    """

    def __init__(
        self,
        settings: Settings,
        credential: Any | None = None,
    ) -> None:
        self._settings = settings
        self._credential = credential
        self._client: BlobServiceClient | None = None
        self._container_ready = False

    def _service_client(self) -> BlobServiceClient:
        """Crea (de forma perezosa) el cliente de Blob Storage.

        Returns:
            Cliente de Azure Blob Storage.

        Raises:
            ConfigurationError: Si no hay URL de cuenta ni cadena de conexión.
        """
        if self._client is not None:
            return self._client
        if self._settings.blob_service_url:
            self._client = BlobServiceClient(
                account_url=self._settings.blob_service_url,
                credential=self._credential,
            )
            return self._client
        if self._settings.blob_connection_string:
            self._client = BlobServiceClient.from_connection_string(
                self._settings.blob_connection_string
            )
            return self._client
        raise ConfigurationError(
            "error.not_configured",
            status_code=503,
            code="storage_not_configured",
            service="LECTURA_BLOB_SERVICE_URL",
        )

    async def _container(self) -> Any:
        """Obtiene el contenedor de fichas, creándolo si no existe.

        Returns:
            Contenedor de Blob Storage ya existente.
        """
        client = self._service_client()
        container = client.get_container_client(self._settings.blob_container)
        if not self._container_ready:
            with contextlib.suppress(ResourceExistsError):
                await container.create_container()
            self._container_ready = True
        return container

    async def upload_image(
        self,
        content: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> str:
        """Sube la imagen de la ficha al contenedor.

        Args:
            content: Bytes de la imagen.
            filename: Nombre original de la imagen.
            content_type: Tipo MIME de la imagen.

        Returns:
            Nombre del blob creado.

        Raises:
            ServiceError: Si Azure devuelve un error al subir el archivo.
        """
        blob_name = build_blob_name(filename)
        container = await self._container()
        logger.info("Subiendo ficha al blob %s", blob_name)
        try:
            await container.upload_blob(
                name=blob_name,
                data=content,
                overwrite=True,
                headers={
                    "Content-Type": content_type,
                    "Cache-Control": "private, max-age=0, no-store",
                },
            )
        except HttpResponseError as exc:
            logger.error("Error al subir el blob %s: %s", blob_name, exc)
            raise ServiceError(
                "error.storage_failed", status_code=502, code="blob_upload_error"
            ) from exc
        return blob_name

    async def read_json(self, blob_name: str) -> dict[str, Any] | None:
        """Lee un blob JSON.

        Args:
            blob_name: Nombre del blob dentro del contenedor.

        Returns:
            Objeto JSON leído o ``None`` si el blob no existe o está vacío.

        Raises:
            ServiceError: Si Azure devuelve un error inesperado.
        """
        container = await self._container()
        blob = container.get_blob_client(blob_name)
        try:
            data = await blob.download_blob()
            payload = await data.readall()
        except Exception as exc:  # el SDK de Azure lanza varios tipos aquí
            if _is_not_found(exc):
                return None
            logger.error("Error leyendo el blob %s: %s", blob_name, exc)
            raise ServiceError(
                "error.storage_failed", status_code=502, code="blob_read_error"
            ) from exc
        if not payload:
            return None
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            logger.error("El blob %s no contiene JSON válido", blob_name)
            raise ServiceError(
                "error.storage_failed", status_code=500, code="blob_invalid_json"
            ) from exc
        return parsed if isinstance(parsed, dict) else None

    async def write_json(self, blob_name: str, payload: dict[str, Any]) -> None:
        """Sobrescribe un blob JSON.

        Args:
            blob_name: Nombre del blob.
            payload: Objeto serializable a JSON.

        Raises:
            ServiceError: Si Azure devuelve un error al escribir.
        """
        container = await self._container()
        blob = container.get_blob_client(blob_name)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            await blob.upload_blob(
                name=blob_name,
                data=body,
                overwrite=True,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        except HttpResponseError as exc:
            logger.error("Error escribiendo el blob %s: %s", blob_name, exc)
            raise ServiceError(
                "error.storage_failed", status_code=502, code="blob_write_error"
            ) from exc

    async def close(self) -> None:
        """Cierra el cliente de Blob Storage."""
        if self._client is not None:
            await self._client.close()
            self._client = None


def _is_not_found(exc: Exception) -> bool:
    """Indica si la excepción corresponde a un recurso inexistente.

    Args:
        exc: Excepción lanzada por el SDK.

    Returns:
        ``True`` si el recurso no existe (404).
    """
    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status_code == 404:
        return True
    error_code = getattr(exc, "error_code", None)
    return isinstance(error_code, str) and error_code.lower() == "blobnotfound"


class InMemoryStorageService:
    """Almacenamiento temporal en memoria (desarrollo, demo y pruebas).

    Mantiene los blobs en un diccionario del proceso: al reiniciar la
    aplicación se pierde el contenido, por lo que solo se usa cuando Azure no
    está configurado.
    """

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def upload_image(
        self,
        content: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> str:
        """Guarda la imagen en memoria.

        Args:
            content: Bytes de la imagen.
            filename: Nombre original de la imagen.
            content_type: Tipo MIME (se ignora).

        Returns:
            Nombre del blob generado.
        """
        blob_name = build_blob_name(filename)
        self._blobs[blob_name] = content
        return blob_name

    async def read_json(self, blob_name: str) -> dict[str, Any] | None:
        """Lee un blob JSON de memoria.

        Args:
            blob_name: Nombre del blob.

        Returns:
            Contenido JSON o ``None`` si no existe.
        """
        payload = self._blobs.get(blob_name)
        if payload is None:
            return None
        parsed = json.loads(payload.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else None

    async def write_json(self, blob_name: str, payload: dict[str, Any]) -> None:
        """Sobrescribe un blob JSON de memoria.

        Args:
            blob_name: Nombre del blob.
            payload: Objeto serializable a JSON.
        """
        self._blobs[blob_name] = json.dumps(payload, ensure_ascii=False).encode("utf-8")
