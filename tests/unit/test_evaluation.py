"""Pruebas de la evaluación de pronunciación."""

from __future__ import annotations

import pytest

from app.services.evaluation import (
    evaluate_pronunciation,
    normalize,
    similarity,
)


def test_exact_match_is_correct() -> None:
    """Una palabra idéntica se considera correcta."""
    result = evaluate_pronunciation("mariposa", "mariposa")

    assert result.correct is True
    assert result.score == 1.0
    assert result.feedback_key == "feedback.perfect"


def test_ignores_case_accents_and_punctuation() -> None:
    """Mayúsculas, tildes y signos no afectan al resultado."""
    result = evaluate_pronunciation("Árbol", "arbol,")

    assert result.correct is True
    assert result.score == 1.0


def test_word_inside_a_phrase_is_accepted() -> None:
    """Si la palabra aparece en la frase transcrita, se acepta."""
    result = evaluate_pronunciation("gos", "el gos rosa")

    assert result.correct is True


def test_close_word_is_not_correct_with_strict_threshold() -> None:
    """Una palabra parecida queda como «casi» si se exige más precisión."""
    result = evaluate_pronunciation("mariposa", "maripossi", threshold=0.95)

    assert result.correct is False
    assert result.feedback_key == "feedback.close"


def test_single_letter_error_in_long_word_is_accepted() -> None:
    """Una palabra larga con un fallo puntual sigue siendo un acierto."""
    result = evaluate_pronunciation("mariposa", "maripossi")

    assert result.correct is True


def test_wrong_word_asks_to_try_again() -> None:
    """Una palabra completamente distinta pide otro intento."""
    result = evaluate_pronunciation("mariposa", "perro")

    assert result.correct is False
    assert result.feedback_key == "feedback.try_again"


def test_empty_spoken_text_is_not_correct() -> None:
    """Sin transcripción no hay acierto."""
    result = evaluate_pronunciation("mariposa", "")

    assert result.correct is False
    assert result.score == 0.0


def test_empty_expected_word_raises() -> None:
    """La palabra esperada es obligatoria."""
    with pytest.raises(ValueError):
        evaluate_pronunciation("   ", "algo")


def test_similarity_is_symmetric_and_bounded() -> None:
    """La similitud se mantiene entre 0 y 1."""
    assert similarity("gato", "gato") == 1.0
    assert 0.0 <= similarity("gato", "pato") <= 1.0
    assert similarity("", "gato") == 0.0


def test_normalize_strips_diacritics() -> None:
    """La normalización quita tildes y signos."""
    assert normalize("  ¡MARIPOSA!  ") == "mariposa"
