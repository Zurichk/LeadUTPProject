"""Pruebas del adaptador de Azure AI Speech."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.core.auth import CognitiveAuth
from app.core.config import Settings
from app.core.errors import ConfigurationError, ServiceError
from app.services.speech import AzureSpeechService

Handler = Callable[[httpx.Request], httpx.Response]


def make_settings(**overrides: object) -> Settings:
    """Crea ajustes mínimos para el servicio de voz.

    Args:
        **overrides: Valores que sobrescriben los ajustes por defecto.

    Returns:
        Ajustes de la aplicación.
    """
    return Settings(speech_region="westeurope", **overrides)  # type: ignore[arg-type]


class KeyAuth(CognitiveAuth):
    """Autenticación con clave estática para las pruebas."""

    async def headers(self) -> dict[str, str]:
        """Devuelve la cabecera de autorización estática.

        Returns:
            Cabecera con la clave de prueba.
        """
        return await super().headers()


async def test_synthesize_uses_the_language_voice() -> None:
    """Cada idioma usa su voz neuronal."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "ca-ES-JoanaNeural" in request.content.decode()
        return httpx.Response(200, content=b"ID3-audio")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = AzureSpeechService(
            make_settings(), KeyAuth(subscription_key="clave"), client
        )
        result = await service.synthesize("mariposa", "ca")

    assert result.audio == b"ID3-audio"
    assert result.voice == "ca-ES-JoanaNeural"
    assert result.content_type == "audio/mpeg"


async def test_synthesize_uses_cache() -> None:
    """La segunda petición de la misma palabra no vuelve a Azure."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"ID3-audio")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = AzureSpeechService(
            make_settings(), KeyAuth(subscription_key="clave"), client
        )
        await service.synthesize("mariposa", "es")
        await service.synthesize("mariposa", "es")

    assert calls == 1


async def test_synthesize_reports_service_errors() -> None:
    """Un error del servicio se traduce a ServiceError."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as client:
        service = AzureSpeechService(
            make_settings(), KeyAuth(subscription_key="clave"), client
        )
        with pytest.raises(ServiceError) as error:
            await service.synthesize("mariposa", "es")

    assert error.value.code == "tts_error"


async def test_synthesize_rejects_empty_audio() -> None:
    """Una respuesta sin audio se considera error."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b""))
    ) as client:
        service = AzureSpeechService(
            make_settings(), KeyAuth(subscription_key="clave"), client
        )
        with pytest.raises(ServiceError):
            await service.synthesize("mariposa", "es")


async def test_recognize_returns_transcription() -> None:
    """El reconocedor devuelve el texto de la mejor hipótesis."""
    payload = {
        "RecognitionStatus": "Success",
        "NBest": [{"DisplayText": "Mika", "Confidence": 0.91}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "language=ca-ES" in str(request.url)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = AzureSpeechService(
            make_settings(), KeyAuth(subscription_key="clave"), client
        )
        result = await service.recognize(b"RIFF-audio", "ca")

    assert result.text == "Mika"
    assert result.confidence == 0.91


async def test_recognize_reports_service_errors() -> None:
    """Un error del reconocedor se traduce a ServiceError."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    ) as client:
        service = AzureSpeechService(
            make_settings(), KeyAuth(subscription_key="clave"), client
        )
        with pytest.raises(ServiceError) as error:
            await service.recognize(b"RIFF-audio", "es")

    assert error.value.code == "stt_error"


async def test_auth_requires_credentials() -> None:
    """Sin credencial ni clave se informa del error de configuración."""
    auth = CognitiveAuth(credential=None, subscription_key=None)

    with pytest.raises(ConfigurationError) as error:
        await auth.headers()

    assert error.value.code == "azure_identity_missing"


async def test_static_key_takes_precedence_over_credential() -> None:
    """En local gana la clave estática: la identidad puede no existir.

    Es el caso real de un portátil sin Azure CLI ni Managed Identity, donde
    ``DefaultAzureCredential`` se construye pero falla al pedir token.
    """

    class FailingCredential:
        """Credencial que siempre falla, como ocurre en local sin identidad."""

        async def get_token(self, *scopes: str, **kwargs: object) -> str:
            """Falla siempre.

            Args:
                *scopes: Ámbitos solicitados.
                **kwargs: Parámetros adicionales.

            Raises:
                RuntimeError: Siempre.
            """
            raise RuntimeError("no hay identidad disponible")

    auth = CognitiveAuth(
        credential=FailingCredential(),  # type: ignore[arg-type]
        subscription_key="clave-estatica",
    )

    assert await auth.headers() == {"Ocp-Apim-Subscription-Key": "clave-estatica"}
