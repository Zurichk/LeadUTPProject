"""Modelos de valor del dominio de OCR."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class OcrWord:
    """Palabra detectada por el OCR.

    Attributes:
        text: Texto reconocido (sin normalizar).
        confidence: Confianza del motor entre 0 y 1.
        bbox: Casilla envolvente en coordenadas normalizadas de la página.
    """

    text: str
    confidence: float = 0.0
    bbox: tuple[float, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Resultado completo de un análisis de imagen.

    Attributes:
        text: Texto plano de la página.
        words: Palabras individuales con su confianza.
        provider: Nombre del proveedor que generó el resultado.
    """

    text: str
    words: tuple[OcrWord, ...] = ()
    provider: str = ""

    @property
    def average_confidence(self) -> float:
        """Confianza media de las palabras detectadas (0 si no hay ninguna)."""
        if not self.words:
            return 0.0
        return sum(word.confidence for word in self.words) / len(self.words)
