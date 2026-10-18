"""Pruebas de los adaptadores de voz y del constructor de SSML."""

from __future__ import annotations

import pytest

from app.core.errors import ServiceError
from app.services.speech import (
    SpeechRecognitionResult,
    UnavailableSpeechService,
    _parse_recognition,
    build_ssml,
)


def test_build_ssml_escapes_special_chars() -> None:
    """Los caracteres especiales se escapan en el documento SSML."""
    ssml = build_ssml("mariposa & sol", "es-ES-ElviraNeural", "es-ES")

    assert "&amp;" in ssml
    assert "es-ES-ElviraNeural" in ssml
    assert ssml.startswith("<speak")


def test_parse_recognition_success() -> None:
    """Se toma la mejor hipótesis de la respuesta correcta."""
    result = _parse_recognition(
        {
            "RecognitionStatus": "Success",
            "NBest": [
                {"DisplayText": "mariposa", "Confidence": 0.87},
                {"DisplayText": "mariposi", "Confidence": 0.2},
            ],
        }
    )

    assert result == SpeechRecognitionResult(text="mariposa", confidence=0.87)


def test_parse_recognition_without_status() -> None:
    """Sin acierto se devuelve el texto vacío."""
    result = _parse_recognition({"RecognitionStatus": "NoMatch"})

    assert result.text == ""
    assert result.confidence == 0.0


def test_parse_recognition_falls_back_to_display_text() -> None:
    """Si no hay NBest se usa ``DisplayText``."""
    result = _parse_recognition({"RecognitionStatus": "Success", "DisplayText": "Hola"})

    assert result.text == "Hola"


async def test_unavailable_speech_service_raises() -> None:
    """El servicio no disponible responde con un error 503."""
    service = UnavailableSpeechService()

    with pytest.raises(ServiceError) as synth_error:
        await service.synthesize("hola", "es")
    with pytest.raises(ServiceError) as recognize_error:
        await service.recognize(b"audio", "es")

    assert synth_error.value.status_code == 503
    assert recognize_error.value.code == "speech_not_configured"
