"""DTOs del flujo de subida de fichas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WordItem(BaseModel):
    """Palabra extraída de la ficha.

    Attributes:
        text: Texto de la palabra.
        language: Idioma del texto (``"es"`` o ``"ca"``).
        confidence: Confianza del OCR (0-1).
    """

    text: str = Field(min_length=1, max_length=40, examples=["mariposa"])
    language: str = Field(default="es", pattern="^(es|ca)$")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SheetResponse(BaseModel):
    """Resultado del análisis de una ficha.

    Attributes:
        blob_name: Nombre del blob donde se guardó la imagen.
        language: Idioma detectado o forzado.
        words: Palabras de lectura detectadas.
        text_length: Longitud del texto reconocido, útil para depurar.
    """

    blob_name: str
    language: str = Field(pattern="^(es|ca)$")
    words: list[WordItem] = Field(default_factory=list)
    text_length: int = 0
