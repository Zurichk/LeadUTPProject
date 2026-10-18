"""Pruebas de la configuración de la aplicación."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import LetterCase, Settings, SpeechBackend


def test_letter_case_defaults_to_both() -> None:
    """Por defecto se muestran mayúscula y minúscula."""
    assert Settings().letter_case == "both"


@pytest.mark.parametrize("mode", ["upper", "lower", "both"])
def test_letter_case_accepts_valid_values(mode: LetterCase) -> None:
    """Los tres modos de letras son válidos."""
    assert Settings(letter_case=mode).letter_case == mode


def test_letter_case_rejects_unknown_value() -> None:
    """Un modo de letras inexistente se rechaza."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"letter_case": "titulo"})


def test_speech_backend_defaults_to_auto() -> None:
    """Por defecto se intenta Azure y se cae al navegador."""
    assert Settings().speech_backend == "auto"


@pytest.mark.parametrize("backend", ["auto", "browser", "azure"])
def test_speech_backend_accepts_valid_values(backend: SpeechBackend) -> None:
    """Los tres modos de voz son válidos."""
    assert Settings(speech_backend=backend).speech_backend == backend


def test_speech_backend_rejects_unknown_value() -> None:
    """Un modo de voz inexistente se rechaza al leer la configuración."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"speech_backend": "microsft"})


def test_max_upload_bytes_is_derived_from_megabytes() -> None:
    """El límite de subida se calcula a partir de los megabytes."""
    settings = Settings(max_upload_mb=5)

    assert settings.max_upload_bytes == 5 * 1024 * 1024


def test_missing_services_lists_only_what_is_absent() -> None:
    """Se informa únicamente de los servicios sin configurar."""
    settings = Settings(
        vision_endpoint="https://vision.example/",
        blob_service_url="https://storage.example/",
        speech_region="westeurope",
    )

    assert settings.missing_services() == []

    partial = Settings(vision_endpoint=None, blob_service_url=None)

    assert len(partial.missing_services()) == 2
