"""OCR de fichas de lectura sobre servicios de Azure AI."""

from __future__ import annotations

import httpx

from app.core.auth import CognitiveAuth
from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.services.ocr.models import OcrResult, OcrWord
from app.services.ocr.ports import OcrPort
from app.services.ocr.providers import (
    AzureDocumentIntelligenceOcr,
    AzureVisionReadOcr,
    DemoOcr,
)
from app.services.ocr.word_extraction import (
    ReadingWord,
    extract_words,
    is_valid_word,
    normalize_word,
)

__all__ = (
    "AzureDocumentIntelligenceOcr",
    "AzureVisionReadOcr",
    "DemoOcr",
    "OcrPort",
    "OcrResult",
    "OcrWord",
    "ReadingWord",
    "create_ocr_service",
    "extract_words",
    "is_valid_word",
    "normalize_word",
)


def create_ocr_service(
    settings: Settings,
    auth: CognitiveAuth,
    client: httpx.AsyncClient,
) -> OcrPort:
    """Construye el adaptador de OCR según la configuración.

    Args:
        settings: Ajustes de la aplicación.
        auth: Proveedor de cabeceras de autenticación.
        client: Cliente HTTP asíncrono compartido.

    Returns:
        Implementación de :class:`OcrPort` lista para usar.

    Raises:
        ConfigurationError: Si falta el endpoint del proveedor configurado.
    """
    if settings.demo_mode:
        return DemoOcr()
    if settings.ocr_provider == "vision":
        if not settings.vision_endpoint:
            raise ConfigurationError(
                "error.not_configured",
                status_code=503,
                code="vision_endpoint_missing",
                service="LECTURA_VISION_ENDPOINT",
            )
        return AzureVisionReadOcr(
            endpoint=settings.vision_endpoint,
            auth=auth,
            client=client,
            api_version=settings.vision_api_version,
        )
    if not settings.document_intelligence_endpoint:
        raise ConfigurationError(
            "error.not_configured",
            status_code=503,
            code="document_intelligence_endpoint_missing",
            service="LECTURA_DOCUMENT_INTELLIGENCE_ENDPOINT",
        )
    return AzureDocumentIntelligenceOcr(
        endpoint=settings.document_intelligence_endpoint,
        auth=auth,
        client=client,
        api_version=settings.document_intelligence_api_version,
        max_wait_seconds=settings.max_ocr_wait_seconds,
    )
