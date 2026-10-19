"""Punto de composición: construye los adaptadores de Azure una sola vez.

Es el único lugar donde se instancian dependencias concretas. El resto de la
aplicación recibe interfaces a través de la inyección de dependencias de
FastAPI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.auth import CognitiveAuth, close_credential, create_credential
from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.services.ocr import OcrPort, create_ocr_service
from app.services.ocr.models import OcrResult
from app.services.profiles import ProfileService
from app.services.speech import (
    AzureSpeechService,
    SpeechPort,
    UnavailableSpeechService,
)
from app.services.storage import (
    BlobStorageService,
    InMemoryStorageService,
    StoragePort,
)
from app.services.translation import (
    FoundryTranslationService,
    HybridTranslationService,
    TranslationPort,
)

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 60.0
CONNECT_TIMEOUT_SECONDS = 15.0


class UnavailableOcrService:
    """OCR no disponible porque faltan credenciales o endpoint."""

    async def read_image(self, image: bytes, *, filename: str) -> OcrResult:
        """Indica que el OCR no está configurado.

        Args:
            image: Bytes de la imagen (no se procesan).
            filename: Nombre de la imagen (no se usa).

        Raises:
            ConfigurationError: Siempre, con el servicio que falta.
        """
        raise ConfigurationError(
            "error.not_configured",
            status_code=503,
            code="ocr_not_configured",
            service="LECTURA_VISION_ENDPOINT",
        )


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    """Dependencias compartidas por toda la aplicación.

    Attributes:
        settings: Ajustes tipados.
        ocr: Servicio de lectura de texto en imágenes.
        speech: Servicio de síntesis y reconocimiento de voz.
        storage: Servicio de almacenamiento de blobs.
        profiles: Caso de uso de perfiles de lectura.
        translation: Servicio opcional de traducción con Foundry.
        http_client: Cliente HTTP asíncrono compartido.
        credential: Credencial de Entra ID, si se pudo crear.
    """

    settings: Settings
    ocr: OcrPort
    speech: SpeechPort
    storage: StoragePort
    profiles: ProfileService
    translation: TranslationPort
    http_client: httpx.AsyncClient
    credential: Any | None = None


async def build_container(settings: Settings) -> ServiceContainer:
    """Construye el contenedor de servicios.

    Args:
        settings: Ajustes de la aplicación.

    Returns:
        Contenedor listo para ser usado por los routers.
    """
    credential = None if settings.demo_mode else await create_credential(settings)
    auth = CognitiveAuth(credential, settings.speech_key)
    # El OCR admite su propia clave estática para desarrollo local.
    ocr_auth = CognitiveAuth(
        credential,
        settings.vision_key or settings.document_intelligence_key,
    )
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
        follow_redirects=True,
    )

    try:
        ocr: OcrPort = create_ocr_service(settings, ocr_auth, http_client)
    except ConfigurationError:
        logger.warning(
            "El OCR no está configurado; las fichas no se podrán leer hasta "
            "ajustar LECTURA_VISION_ENDPOINT."
        )
        ocr = UnavailableOcrService()

    storage: StoragePort = (
        InMemoryStorageService()
        if not settings.storage_configured
        else BlobStorageService(settings, credential)
    )
    if not settings.storage_configured:
        logger.warning(
            "Blob Storage no está configurado; las imágenes se guardarán solo "
            "en memoria."
        )

    speech: SpeechPort = (
        UnavailableSpeechService()
        if settings.demo_mode or settings.speech_backend == "browser"
        else AzureSpeechService(settings, auth, http_client)
    )

    model_translator: TranslationPort | None = None
    if settings.translation_configured and settings.foundry_endpoint:
        model_translator = FoundryTranslationService(
            endpoint=settings.foundry_endpoint,
            deployment=settings.foundry_deployment,
            auth=auth,
            client=http_client,
            api_key=settings.foundry_api_key,
            timeout_seconds=settings.foundry_timeout_seconds,
            cache_size=settings.translation_cache_size,
        )
        logger.info(
            "Traducción con modelo: %s (%s)",
            settings.foundry_deployment,
            settings.foundry_endpoint,
        )
    # El diccionario propio es siempre el camino preferente; el modelo solo
    # interviene para las palabras que el diccionario no conoce.
    translation: TranslationPort = HybridTranslationService(
        model=model_translator,
        cache_size=settings.translation_cache_size,
    )

    return ServiceContainer(
        settings=settings,
        ocr=ocr,
        speech=speech,
        storage=storage,
        profiles=ProfileService(storage, settings.profiles_blob_name),
        translation=translation,
        http_client=http_client,
        credential=credential,
    )


async def shutdown_container(container: ServiceContainer) -> None:
    """Cierra los recursos del contenedor.

    Args:
        container: Contenedor a cerrar.
    """
    await container.http_client.aclose()
    close = getattr(container.storage, "close", None)
    if close is not None:
        result = close()
        if hasattr(result, "__await__"):
            await result
    await close_credential(container.credential)
    logger.info("Contenedor de servicios cerrado")


__all__ = (
    "ServiceContainer",
    "build_container",
    "shutdown_container",
)
