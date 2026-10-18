"""DTOs de la traducción de palabras de la ficha."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_WORDS = 30
MAX_WORD_LENGTH = 40


class TranslationRequest(BaseModel):
    """Petición de traducción de las palabras de una ficha.

    Attributes:
        words: Palabras extraídas del OCR.
        source_language: Idioma de la ficha.
        target_language: Idioma al que se traducen.
    """

    words: list[str] = Field(min_length=1, max_length=MAX_WORDS)
    source_language: str = Field(default="es", pattern="^(es|ca)$")
    target_language: str = Field(default="ca", pattern="^(es|ca)$")

    @field_validator("words")
    @classmethod
    def clean_words(cls, value: list[str]) -> list[str]:
        """Limpia y deduplica las palabras a traducir.

        Args:
            value: Palabras recibidas.

        Returns:
            Lista de palabras no vacías y sin repetir, conservando el orden.

        Raises:
            ValueError: Si no queda ninguna palabra válida.
        """
        cleaned: list[str] = []
        seen: set[str] = set()
        for word in value:
            item = " ".join(word.split())[:MAX_WORD_LENGTH]
            key = item.casefold()
            if item and key not in seen:
                seen.add(key)
                cleaned.append(item)
        if not cleaned:
            raise ValueError("No hay palabras que traducir")
        return cleaned


class WordTranslation(BaseModel):
    """Par de traducción de una palabra.

    Attributes:
        word: Palabra original de la ficha.
        translated: Palabra en el idioma de destino.
    """

    word: str
    translated: str


class TranslationResponse(BaseModel):
    """Resultado de la traducción.

    Attributes:
        translations: Pares (original, traducción) en orden.
        target_language: Idioma de destino effective.
        from_cache: Si la respuesta se sirvió desde la caché del servidor.
    """

    translations: list[WordTranslation]
    target_language: str = Field(pattern="^(es|ca)$")
    from_cache: bool = False
