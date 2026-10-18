"""Extracción de palabras de lectura a partir del resultado del OCR.

De una ficha fotografiada no interesa todo el texto: nos quedamos con las
palabras cortas y con significado, descartando artículos, preposiciones y
basura típica del reconocimiento óptico.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.core.i18n import detect_language
from app.services.ocr.models import OcrResult

#: Palabras vacías o demasiado frecuentes para ser una ficha de lectura.
STOPWORDS: frozenset[str] = frozenset(
    {
        # Castellano
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "lo",
        "de",
        "del",
        "al",
        "a",
        "y",
        "e",
        "o",
        "u",
        "con",
        "sin",
        "por",
        "para",
        "que",
        "qué",
        "en",
        "es",
        "son",
        "está",
        "estan",
        "están",
        "se",
        "su",
        "sus",
        "le",
        "les",
        "mi",
        "tu",
        "este",
        "esta",
        "esto",
        "estos",
        "estas",
        # Valenciano / catalán
        "els",
        "uns",
        "unes",
        "des",
        "als",
        "i",
        "amb",
        "sense",
        "per",
        "perquè",
        "perque",
        "està",
        "aquest",
        "aquesta",
        "aquests",
        "aquestes",
        "seu",
        "seva",
    }
)

#: Caracteres permitidos en una palabra (incluye ``l·l`` y diacríticos).
_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzàáèéíïòóúüñç·")


@dataclass(frozen=True, slots=True)
class ReadingWord:
    """Palabra lista para mostrar en una tarjeta.

    Attributes:
        text: Texto de la palabra tal y como aparece en la ficha.
        language: Idioma (``"es"`` o ``"ca"``) del texto.
        confidence: Confianza del OCR que detectó la palabra.
    """

    text: str
    language: str
    confidence: float = 0.0


def normalize_word(value: str) -> str:
    """Limpia un token del OCR para poder compararlo.

    Args:
        value: Token original.

    Returns:
        Token en minúsculas, sin signos de puntuación ni espacios sobrantes.
    """
    cleaned = "".join(ch for ch in value.strip() if unicodedata.category(ch)[0] != "P")
    return unicodedata.normalize("NFC", cleaned).strip().casefold()


def is_valid_word(
    value: str,
    *,
    min_length: int,
    max_length: int,
) -> bool:
    """Indica si un token puede ser una palabra de lectura.

    Args:
        value: Token normalizado.
        min_length: Longitud mínima aceptada.
        max_length: Longitud máxima aceptada.

    Returns:
        ``True`` si el token es una palabra con letras válidas.
    """
    if not (min_length <= len(value) <= max_length):
        return False
    if value in STOPWORDS:
        return False
    return all(ch in _ALLOWED_CHARS for ch in value)


def extract_words(
    result: OcrResult,
    *,
    language: str | None = None,
    min_length: int = 2,
    max_length: int = 15,
    min_confidence: float = 0.5,
    max_words: int = 12,
) -> list[ReadingWord]:
    """Selecciona las palabras de lectura de un resultado de OCR.

    Se prefieren las palabras individuales con confianza (Vision y Document
    Intelligence las proporcionan); si no hay ninguna, se trocea el texto
    plano.

    Args:
        result: Resultado del OCR.
        language: Idioma forzado; si es ``None`` se detecta automáticamente.
        min_length: Longitud mínima de palabra.
        max_length: Longitud máxima de palabra.
        min_confidence: Confianza mínima del OCR.
        max_words: Número máximo de palabras devueltas.

    Returns:
        Lista de palabras únicas en el orden en que aparecen en la ficha.
    """
    candidates: list[tuple[str, float]] = [
        (word.text, word.confidence)
        for word in result.words
        if word.confidence >= min_confidence
    ]
    if not candidates:
        candidates = [(token, 0.0) for token in result.text.split()]

    resolved_language = language or detect_language(result.text)
    seen: set[str] = set()
    words: list[ReadingWord] = []
    for candidate, confidence in candidates:
        normalized = normalize_word(candidate)
        if not is_valid_word(normalized, min_length=min_length, max_length=max_length):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        words.append(
            ReadingWord(
                text=candidate.strip(" .,:;"),
                language=resolved_language,
                confidence=confidence,
            )
        )
        if len(words) >= max_words:
            break
    return words
