"""Pruebas de la configuración y de los proveedores de OCR."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.core.auth import CognitiveAuth
from app.core.config import Settings
from app.core.errors import ConfigurationError, ServiceError
from app.services.ocr import (
    AzureVisionReadOcr,
    DemoOcr,
    create_ocr_service,
)
from app.services.ocr.providers import AzureDocumentIntelligenceOcr


class KeyAuth(CognitiveAuth):
    """Autenticación con clave estática para las pruebas."""

    def __init__(self) -> None:
        super().__init__(credential=None, subscription_key="clave-de-prueba")

    async def headers(self) -> dict[str, str]:
        """Devuelve la cabecera de clave.

        Returns:
            Cabecera con la clave de prueba.
        """
        return await super().headers()


Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler) -> httpx.AsyncClient:
    """Crea un cliente HTTP con un manejador simulado.

    Args:
        handler: Función que responde a la petición.

    Returns:
        Cliente HTTP asíncrono.
    """
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_vision_reads_words() -> None:
    """Se extraen las palabras de la respuesta real de Azure AI Vision.

    La estructura devuelta por el servicio es ``readResult.blocks[].lines[]
    .words[]`` (sin nivel ``pages``), con ``boundingPolygon`` como lista de
    objetos ``{"x": .., "y": ..}``. Replica una respuesta capturada del
    servicio real para no volver a asumir una forma equivocada.
    """
    payload = {
        "modelVersion": "2023-10-01",
        "metadata": {"width": 1000, "height": 2300},
        "readResult": {
            "blocks": [
                {
                    "lines": [
                        {
                            "text": "Mika gos",
                            "words": [
                                {
                                    "text": "Mika",
                                    "confidence": 0.998,
                                    "boundingPolygon": [
                                        {"x": 57, "y": 49},
                                        {"x": 139, "y": 50},
                                    ],
                                },
                                {
                                    "text": "gos",
                                    "confidence": 0.987,
                                    "boundingPolygon": [
                                        {"x": 180, "y": 49},
                                        {"x": 260, "y": 50},
                                    ],
                                },
                            ],
                        }
                    ]
                }
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "features=read" in str(request.url)
        return httpx.Response(200, json=payload)

    async with make_client(handler) as client:
        ocr = AzureVisionReadOcr("https://vision.example", KeyAuth(), client)
        result = await ocr.read_image(b"image", filename="ficha.jpg")

    assert result.provider == "vision"
    assert [word.text for word in result.words] == ["Mika", "gos"]
    assert result.words[0].bbox == ((57.0, 49.0), (139.0, 50.0))
    assert result.average_confidence > 0.98


async def test_vision_reads_nested_pages_shape() -> None:
    """También se admite la variante con ``analyzeResult.readResult.pages``."""
    payload = {
        "analyzeResult": {
            "readResult": {
                "pages": [
                    {
                        "blocks": [
                            {
                                "lines": [
                                    {"words": [{"text": "flor", "confidence": 0.9}]}
                                ]
                            }
                        ]
                    }
                ]
            }
        }
    }

    async with make_client(lambda request: httpx.Response(200, json=payload)) as client:
        ocr = AzureVisionReadOcr("https://vision.example", KeyAuth(), client)
        result = await ocr.read_image(b"image", filename="ficha.jpg")

    assert [word.text for word in result.words] == ["flor"]


async def test_vision_service_error() -> None:
    """Un error del servicio se traduce a ServiceError."""
    async with make_client(lambda request: httpx.Response(500)) as client:
        ocr = AzureVisionReadOcr("https://vision.example", KeyAuth(), client)
        with pytest.raises(ServiceError) as error:
            await ocr.read_image(b"image", filename="ficha.jpg")

    assert error.value.code == "vision_error"


async def test_vision_empty_result() -> None:
    """Una ficha sin palabras se informa como vacía."""
    payload: dict[str, object] = {"analyzeResult": {"readResult": {"pages": []}}}

    async with make_client(lambda request: httpx.Response(200, json=payload)) as client:
        ocr = AzureVisionReadOcr("https://vision.example", KeyAuth(), client)
        with pytest.raises(ServiceError) as error:
            await ocr.read_image(b"image", filename="ficha.jpg")

    assert error.value.code == "empty_sheet"


async def test_document_intelligence_polls_operation() -> None:
    """Se consulta ``operation-location`` hasta obtener el resultado."""
    payload: dict[str, object] = {
        "analyzeResult": {
            "pages": [{"lines": [{"words": [{"content": "gos", "confidence": 0.88}]}]}]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, headers={"operation-location": "https://di/op"})
        return httpx.Response(200, json={"status": "succeeded", **payload})

    async with make_client(handler) as client:
        ocr = AzureDocumentIntelligenceOcr("https://di.example", KeyAuth(), client)
        result = await ocr.read_image(b"image", filename="ficha.jpg")

    assert result.provider == "document_intelligence"
    assert result.words[0].text == "gos"


async def test_demo_ocr_returns_words() -> None:
    """El OCR de demostración devuelve palabras sin llamar a Azure."""
    result = await DemoOcr().read_image(b"image", filename="ficha.jpg")

    assert result.provider == "demo"
    assert result.words


async def test_factory_requires_endpoint() -> None:
    """Sin endpoint se informa de la configuración que falta."""
    settings = Settings(vision_endpoint=None)

    async with httpx.AsyncClient() as client:
        with pytest.raises(ConfigurationError):
            create_ocr_service(settings, KeyAuth(), client)


async def test_factory_returns_demo_in_demo_mode() -> None:
    """En modo demostración se usa el OCR simulado."""
    async with httpx.AsyncClient() as client:
        service = create_ocr_service(Settings(demo_mode=True), KeyAuth(), client)

    assert isinstance(service, DemoOcr)


async def test_settings_report_missing_services() -> None:
    """Los ajustes avisan de lo que falta por configurar."""
    settings = Settings(vision_endpoint=None, blob_service_url=None)

    missing = settings.missing_services()

    assert any("OCR" in item for item in missing)
    assert any("blob" in item for item in missing)
