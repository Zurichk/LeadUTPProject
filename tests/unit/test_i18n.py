"""Pruebas de la internacionalización."""

from __future__ import annotations

import pytest

from app.core.i18n import TRANSLATIONS, Translator, detect_language, normalize_language


def test_both_catalogs_have_the_same_keys() -> None:
    """Las claves de castellano y valenciano están sincronizadas."""
    assert set(TRANSLATIONS["es"]) == set(TRANSLATIONS["ca"])


def test_translator_falls_back_to_key() -> None:
    """Una clave inexistente se devuelve tal cual."""
    assert Translator("es").t("clave.inventada") == "clave.inventada"


def test_translator_interpolates_parameters() -> None:
    """Los parámetros se inyectan en el mensaje."""
    message = Translator("es").t("error.file_size", max=12)

    assert message == "La imagen es demasiado grande (máximo 12 MB)."


def test_translator_uses_language() -> None:
    """Cada idioma devuelve su propio mensaje."""
    assert Translator("es").t("feedback.perfect") == "¡Muy bien!"
    assert Translator("ca").t("feedback.perfect") == "Molt bé!"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("es-ES", "es"),
        ("ca-ES", "ca"),
        ("Valenciano", "ca"),
        ("valencià", "ca"),
        ("EN", "es"),
        (None, "es"),
        ("", "es"),
    ],
)
def test_normalize_language(value: str | None, expected: str) -> None:
    """Se normalizan las etiquetas de idioma habituales."""
    assert normalize_language(value) == expected


def test_detect_language_spanish() -> None:
    """El castellano se detecta correctamente."""
    assert detect_language("La niña come una manzana con su mamá") == "es"


def test_detect_language_valencian() -> None:
    """El valenciano se detecta por los caracteres y palabras típicas."""
    assert detect_language("El gos és molt bo i juga amb la pilota") == "ca"


def test_detect_language_defaults_to_spanish() -> None:
    """Sin señales claras se devuelve el castellano."""
    assert detect_language("Mika Nube 123") == "es"
