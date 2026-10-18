"""Evaluación de la pronunciación comparando lo reconocido con la palabra.

La comparación es tolerante (no distingue tildes, ignora mayúsculas y
puntuación) porque el objetivo es reforzar a una niña de 5 años, no
reprobarla, pero exige acertar la mayor parte de las letras.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from app.core.i18n import strip_accents
from app.services.ocr.word_extraction import normalize_word

#: Similitud mínima (0-1) para considerar correcta una pronunciación.
DEFAULT_MATCH_THRESHOLD = 0.8


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Resultado de evaluar una pronunciación.

    Attributes:
        correct: ``True`` si la pronunciación se considera correcta.
        score: Similitud entre 0 y 1.
        expected: Palabra esperada normalizada.
        spoken: Texto reconocido normalizado.
        feedback_key: Clave traducible del mensaje de refuerzo.
    """

    correct: bool
    score: float
    expected: str
    spoken: str
    feedback_key: str


def similarity(expected: str, spoken: str) -> float:
    """Calcula la similitud entre la palabra esperada y la reconocida.

    Args:
        expected: Palabra esperada ya normalizada.
        spoken: Texto reconocido ya normalizado.

    Returns:
        Similitud entre 0.0 y 1.0.
    """
    if not expected or not spoken:
        return 0.0
    if expected == spoken:
        return 1.0
    if sorted(expected) == sorted(spoken):
        return 1.0
    return SequenceMatcher(None, expected, spoken).ratio()


def normalize(text: str) -> str:
    """Normaliza un texto para poder compararlo de forma tolerante.

    Args:
        text: Texto de entrada.

    Returns:
        Texto en minúsculas, sin tildes, signos ni espacios duplicados.
    """
    return normalize_word(strip_accents(text))


def evaluate_pronunciation(
    expected: str,
    spoken: str,
    *,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> EvaluationResult:
    """Compara el texto reconocido con la palabra esperada.

    Args:
        expected: Palabra objetivo de la tarjeta.
        spoken: Texto devuelto por el reconocedor de voz.
        threshold: Similitud mínima para considerar correcta la lectura.

    Returns:
        Resultado con la puntuación y el mensaje de refuerzo.

    Raises:
        ValueError: Si la palabra esperada está vacía.
    """
    normalized_expected = normalize(expected)
    normalized_spoken = normalize(spoken)
    if not normalized_expected:
        raise ValueError("La palabra esperada no puede estar vacía")

    score = similarity(normalized_expected, normalized_spoken)
    contains_word = normalized_expected in normalized_spoken.split()
    correct = score >= threshold or contains_word
    if correct:
        feedback_key = "feedback.perfect"
    elif score >= threshold * 0.75:
        feedback_key = "feedback.close"
    else:
        feedback_key = "feedback.try_again"
    return EvaluationResult(
        correct=correct,
        score=round(score, 3),
        expected=normalized_expected,
        spoken=normalized_spoken,
        feedback_key=feedback_key,
    )
