"""Pruebas de la extracción de palabras de lectura."""

from __future__ import annotations

from app.services.ocr.models import OcrResult, OcrWord
from app.services.ocr.word_extraction import (
    extract_words,
    is_valid_word,
    normalize_word,
)


def make_result(words: list[tuple[str, float]], text: str = "") -> OcrResult:
    """Construye un resultado de OCR simulado.

    Args:
        words: Pares (texto, confianza).
        text: Texto plano alternativo.

    Returns:
        Resultado de OCR listo para la extracción.
    """
    ocr_words = tuple(
        OcrWord(text=word, confidence=confidence) for word, confidence in words
    )
    return OcrResult(text=text or " ".join(word for word, _ in words), words=ocr_words)


def test_extracts_reading_words() -> None:
    """Se extraen las palabras significativas en orden."""
    result = make_result([("Mika", 0.98), ("té", 0.9), ("gos", 0.95), ("rosa", 0.9)])

    words = extract_words(result, min_length=2, max_length=15)

    assert [word.text for word in words] == ["Mika", "té", "gos", "rosa"]


def test_removes_stopwords_and_duplicates() -> None:
    """Se descartan palabras vacías y repeticiones."""
    result = make_result([("el", 0.9), ("gos", 0.9), ("gos", 0.9), ("gato", 0.9)])

    words = extract_words(result)

    assert [word.text for word in words] == ["gos", "gato"]


def test_filters_low_confidence_words() -> None:
    """Las palabras con poca confianza se descartan."""
    result = make_result([("gos", 0.9), ("inventado", 0.2)])

    words = extract_words(result, min_confidence=0.5)

    assert [word.text for word in words] == ["gos"]


def test_respects_max_words() -> None:
    """Se limita el número de tarjetas."""
    result = make_result([("uno", 0.9), ("dos", 0.9), ("tres", 0.9)])

    words = extract_words(result, max_words=2)

    assert len(words) == 2


def test_falls_back_to_plain_text() -> None:
    """Si no hay palabras, se trocea el texto plano."""
    result = OcrResult(text="Hola que tal estas")

    words = extract_words(result)

    assert [word.text for word in words] == ["Hola", "tal"]


def test_detects_valencian_text() -> None:
    """El idioma por defecto se detecta a partir del texto."""
    result = make_result([("gos", 0.9), ("perro", 0.9)], text="El gos és molt bo")

    words = extract_words(result)

    assert words[0].language == "ca"


def test_forced_language_overrides_detection() -> None:
    """Se puede forzar el idioma de la ficha."""
    result = make_result([("gos", 0.9)], text="El gos és molt bo")

    words = extract_words(result, language="es")

    assert words[0].language == "es"


def test_is_valid_word_rules() -> None:
    """Se rechazan tokens con números o demasiado largos."""
    assert is_valid_word("gos", min_length=2, max_length=15) is True
    assert is_valid_word("a", min_length=2, max_length=15) is False
    assert is_valid_word("12ab", min_length=2, max_length=15) is False
    assert is_valid_word("perro", min_length=2, max_length=4) is False


def test_normalize_word_removes_punctuation() -> None:
    """La normalización quita signos y baja a minúsculas."""
    assert normalize_word("  Hola,  ") == "hola"
