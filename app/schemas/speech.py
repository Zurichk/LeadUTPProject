"""DTOs de los servicios de voz."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_ALLOWED_EXTRA_CHARS = set("' -·")


def validate_pronounceable(value: str) -> str:
    """Comprueba que el texto se pueda pronunciar de forma segura.

    Solo se admiten letras, dígitos y los separadores habituales de las fichas
    de lectura (``-``, ``'`` y el punto medio de ``l·l``).

    Args:
        value: Texto de la palabra.

    Returns:
        Texto validado y recortado.

    Raises:
        ValueError: Si el texto está vacío o contiene caracteres no permitidos.
    """
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("El texto no puede estar vacío")
    for char in cleaned:
        if not (char.isalnum() or char in _ALLOWED_EXTRA_CHARS):
            raise ValueError(f"Caracter no permitido: {char!r}")
    return cleaned


class TtsRequest(BaseModel):
    """Petición de síntesis de voz.

    Attributes:
        word: Palabra a pronunciar.
        language: Idioma de la locución.
        voice: Voz neuronal opcional.
    """

    word: str = Field(min_length=1, max_length=40)
    language: str = Field(default="es", pattern="^(es|ca)$")
    voice: str | None = Field(default=None, max_length=64)

    _validate_word = field_validator("word")(validate_pronounceable)


class EvaluationRequest(BaseModel):
    """Petición de evaluación de una pronunciación.

    Attributes:
        expected_word: Palabra de la tarjeta.
        spoken_text: Texto reconocido por el micrófono.
        language: Idioma de la ficha.
    """

    expected_word: str = Field(min_length=1, max_length=40)
    spoken_text: str = Field(default="", max_length=200)
    language: str = Field(default="es", pattern="^(es|ca)$")

    _validate_word = field_validator("expected_word")(validate_pronounceable)


class EvaluationResponse(BaseModel):
    """Respuesta de la evaluación de pronunciación.

    Attributes:
        correct: Si la pronunciación se considera correcta.
        score: Similitud entre 0 y 1.
        message: Mensaje de refuerzo ya traducido.
        feedback_key: Clave del mensaje (para depurar).
        heard: Texto reconocido, ya normalizado.
    """

    correct: bool
    score: float = Field(ge=0.0, le=1.0)
    message: str
    feedback_key: str
    heard: str = ""


class RecognitionResponse(BaseModel):
    """Respuesta del reconocedor de voz del servidor.

    Attributes:
        text: Texto reconocido.
        confidence: Confianza entre 0 y 1.
        language: Idioma usado.
    """

    text: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    language: str = "es"
