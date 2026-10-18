"""Pruebas del arranque de la aplicación (punto de composición)."""

from __future__ import annotations

import pytest

from app.container import build_container
from app.core.config import Settings
from app.core.errors import ConfigurationError, ServiceError


async def test_container_accepts_static_keys_for_local_development() -> None:
    """Sin identidad, las claves estáticas permiten trabajar en local."""
    settings = Settings(
        vision_endpoint="https://vision.example/",
        vision_key="clave-vision",
        speech_region="westeurope",
        speech_key="clave-speech",
        foundry_endpoint="https://cuenta.openai.azure.com/openai/v1",
        foundry_deployment="Phi-4-mini-instruct",
        foundry_api_key="clave-foundry",
        translation_enabled=True,
    )

    container = await build_container(settings)
    try:
        assert container.ocr is not None
        assert container.translation is not None
    finally:
        await container.http_client.aclose()


async def test_container_builds_in_demo_mode_without_keys() -> None:
    """El modo demo arranca sin ninguna credencial."""
    container = await build_container(Settings(demo_mode=True))
    try:
        assert container.ocr is not None
        assert container.translation is not None
    finally:
        await container.http_client.aclose()


async def test_ocr_is_unavailable_without_configuration() -> None:
    """Sin endpoint ni identidad, el OCR informa del fallo al usarse."""
    container = await build_container(Settings(vision_endpoint=None))
    try:
        with pytest.raises(ConfigurationError):
            await container.ocr.read_image(b"imagen", filename="ficha.jpg")
    finally:
        await container.http_client.aclose()


async def test_translation_is_unavailable_without_configuration() -> None:
    """Sin Foundry configurado, la traducción indica que no está disponible."""
    container = await build_container(Settings(translation_enabled=False))
    try:
        with pytest.raises(ServiceError) as error:
            await container.translation.translate(["casa"], "es", "ca")
    finally:
        await container.http_client.aclose()

    assert error.value.code == "translation_not_configured"
    assert error.value.status_code == 503
