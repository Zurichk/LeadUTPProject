"""Pruebas del servicio de traducción con Azure AI Foundry."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from app.core.auth import CognitiveAuth
from app.core.errors import ServiceError
from app.services.translation import (
    FoundryTranslationService,
    UnavailableTranslationService,
    parse_translations,
)

Handler = Callable[[httpx.Request], httpx.Response]

ENDPOINT = "https://cuenta.openai.azure.com/openai/v1"
WORDS = ["casa", "perro", "mariposa"]


def make_service(handler: Handler, **overrides: object) -> FoundryTranslationService:
    """Crea el servicio con un cliente HTTP simulado.

    Args:
        handler: Función que responde a la petición.
        **overrides: Valores adicionales para el constructor.

    Returns:
        Servicio listo para probar.
    """
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return FoundryTranslationService(
        endpoint=ENDPOINT,
        deployment="Phi-4-mini-instruct",
        auth=CognitiveAuth(subscription_key="clave"),
        client=client,
        api_key="clave-local",
        **overrides,  # type: ignore[arg-type]
    )


def chat_response(content: str) -> httpx.Response:
    """Construye una respuesta de chat con el contenido indicado.

    Args:
        content: Texto generado por el modelo.

    Returns:
        Respuesta HTTP con el formato de Azure OpenAI v1.
    """
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"total_tokens": 42},
        },
    )


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('["casa","gos","papallona"]', ["casa", "gos", "papallona"]),
        ('{"words": ["casa","gos","papallona"]}', ["casa", "gos", "papallona"]),
        ('Aqui van: ["casa","gos","papallona"] y listo', ["casa", "gos", "papallona"]),
        ("1. casa\n2. gos\n3. papallona", ["casa", "gos", "papallona"]),
        (
            "casa -> casa\nperro -> gos\nmariposa -> papallona",
            ["casa", "gos", "papallona"],
        ),
        (
            "1. casa -> casa\n2. perro -> gos\n3. mariposa -> papallona",
            ["casa", "gos", "papallona"],
        ),
        (
            "La traducción es:\ncasa - casa\nperro - gos\nmariposa - papallona",
            ["casa", "gos", "papallona"],
        ),
        ('"casa", "gos", "papallona"', ["casa", "gos", "papallona"]),
    ],
)
def test_parse_translations_accepts_common_formats(
    content: str, expected: list[str]
) -> None:
    """Se entienden JSON, listas numeradas y listas entre comillas."""
    assert parse_translations(content, 3) == expected


@pytest.mark.parametrize(
    "content",
    [
        "La traducción no es posible porque el texto está en chino.",
        '["solo","dos"]',
        "",
    ],
)
def test_parse_translations_rejects_unusable_answers(content: str) -> None:
    """Una respuesta sin el número esperado de elementos se descarta."""
    assert parse_translations(content, 3) == []


async def test_translate_returns_pairs_in_order() -> None:
    """Las traducciones se devuelven en el orden de entrada."""

    def handler(request: httpx.Request) -> httpx.Response:
        return chat_response('["casa","gos","papallona"]')

    service = make_service(handler)
    result = await service.translate(WORDS, "es", "ca")

    assert [pair[1] for pair in result.pairs] == ["casa", "gos", "papallona"]
    assert [pair[0] for pair in result.pairs] == WORDS
    assert result.from_cache is False


async def test_translate_uses_the_cache() -> None:
    """La segunda llamada con las mismas palabras no vuelve al modelo."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return chat_response('["casa","gos","papallona"]')

    service = make_service(handler)
    await service.translate(WORDS, "es", "ca")
    second = await service.translate(WORDS, "es", "ca")

    assert calls == 1
    assert second.from_cache is True


async def test_translate_only_requests_missing_words() -> None:
    """Solo se piden al modelo las palabras que no están en caché."""
    user_messages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        user_messages.append(payload["messages"][-1]["content"])
        return chat_response("gos -> gos")

    service = make_service(handler)
    await service.translate(["casa"], "es", "ca")
    await service.translate(["casa", "perro"], "es", "ca")

    assert len(user_messages) == 2
    assert user_messages[1].endswith("perro")
    assert "casa" not in user_messages[1].splitlines()[-1]


async def test_translate_fails_when_answer_is_unusable() -> None:
    """Si el modelo no devuelve la lista, se informa del error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return chat_response("Perdón, no puedo ayudarte con eso.")

    service = make_service(handler)
    with pytest.raises(ServiceError) as error:
        await service.translate(WORDS, "es", "ca")

    assert error.value.code == "translation_unparsable"


async def test_translate_reports_service_errors() -> None:
    """Un error HTTP del modelo se traduce a ServiceError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "throttled"}})

    service = make_service(handler)
    with pytest.raises(ServiceError) as error:
        await service.translate(WORDS, "es", "ca")

    assert error.value.code == "translation_error"


async def test_translate_handles_timeout() -> None:
    """Un arranque en frío largo no rompe la aplicación."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    service = make_service(handler)
    with pytest.raises(ServiceError) as error:
        await service.translate(WORDS, "es", "ca")

    assert error.value.code == "translation_timeout"
    assert error.value.status_code == 504


async def test_empty_words_returns_empty_result() -> None:
    """Sin palabras no se llama al modelo."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no debería llamarse al modelo")

    service = make_service(handler)
    result = await service.translate([], "es", "ca")

    assert result.pairs == ()


async def test_unavailable_service_reports_configuration() -> None:
    """Sin Foundry configurado se responde 503."""
    with pytest.raises(ServiceError) as error:
        await UnavailableTranslationService().translate(WORDS, "es", "ca")

    assert error.value.code == "translation_not_configured"
    assert error.value.status_code == 503
