"""Pruebas de integración del endpoint de traducción."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import ServiceError
from tests.conftest import FakeTranslation


def test_translate_words_returns_pairs(client: TestClient) -> None:
    """Las palabras se traducen manteniendo el orden."""
    response = client.post(
        "/api/translate-words",
        json={
            "words": ["casa", "perro"],
            "source_language": "es",
            "target_language": "ca",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_language"] == "ca"
    assert payload["translations"] == [
        {"word": "casa", "translated": "casa-ca"},
        {"word": "perro", "translated": "perro-ca"},
    ]


def test_translate_words_deduplicates(
    client: TestClient, translation: FakeTranslation
) -> None:
    """Las palabras repetidas se limpian antes de traducir."""
    response = client.post(
        "/api/translate-words",
        json={
            "words": ["casa", "CASA", " casa ", "perro"],
            "source_language": "es",
            "target_language": "ca",
        },
    )

    assert response.status_code == 200
    assert [item["word"] for item in response.json()["translations"]] == [
        "casa",
        "perro",
    ]
    assert translation.calls[0][0] == ["casa", "perro"]


def test_translate_words_validates_input(client: TestClient) -> None:
    """Una lista vacía o demasiado larga se rechaza."""
    empty = client.post(
        "/api/translate-words",
        json={"words": ["  "], "source_language": "es", "target_language": "ca"},
    )
    too_many = client.post(
        "/api/translate-words",
        json={
            "words": [f"palabra{index}" for index in range(31)],
            "source_language": "es",
            "target_language": "ca",
        },
    )

    assert empty.status_code == 422
    assert too_many.status_code == 422


def test_translate_words_reports_service_failure(
    client: TestClient, translation: FakeTranslation
) -> None:
    """Un fallo del modelo se traduce a un error 502."""
    translation.fail_with = ServiceError(
        "error.generic", status_code=502, code="translation_error"
    )

    response = client.post(
        "/api/translate-words",
        json={"words": ["casa"], "source_language": "es", "target_language": "ca"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "translation_error"
