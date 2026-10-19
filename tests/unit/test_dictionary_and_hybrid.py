"""Pruebas del diccionario y del traductor híbrido."""

from __future__ import annotations

import pytest

from app.core.errors import ServiceError
from app.services.dictionary import INDEX, WORD_PAIRS, lookup, lookup_direct
from app.services.translation import (
    HybridTranslationService,
    TranslationResult,
    is_plausible_translation,
)


class RecordingModel:
    """Modelo simulado que registra lo que se le pide.

    Args:
        translations: Traducciones a devolver por palabra.
        fail_with: Excepción a lanzar si se quiere simular un fallo.
    """

    def __init__(
        self,
        translations: dict[str, str] | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        self.translations = translations or {}
        self.fail_with = fail_with
        self.calls: list[list[str]] = []

    async def translate(
        self,
        words: list[str],
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """Devuelve traducciones simuladas.

        Args:
            words: Palabras solicitadas.
            source_language: Idioma de partida.
            target_language: Idioma de destino.

        Returns:
            Resultado con las traducciones conocidas.

        Raises:
            Exception: La indicada en ``fail_with``, si se configuró.
        """
        self.calls.append(list(words))
        if self.fail_with is not None:
            raise self.fail_with
        return TranslationResult(
            pairs=tuple((word, self.translations.get(word, word)) for word in words)
        )


@pytest.mark.parametrize(
    ("word", "target", "expected"),
    [
        ("perro", "ca", "gos"),
        ("gos", "es", "perro"),
        ("LECHE", "ca", "llet"),
        ("llet", "es", "leche"),
        ("  mariposa  ", "ca", "papallona"),
        ("flor", "ca", "flor"),
        ("dels", "es", "de los"),
        ("menuda", "es", "pequeña"),
        ("rossa", "es", "roja"),
        ("pequeña", "ca", "menuda"),
        ("parc", "es", "parque"),
        ("coche", "ca", "cotxe"),
    ],
)
def test_lookup_translates_both_directions(
    word: str, target: str, expected: str
) -> None:
    """El diccionario traduce en ambos sentidos e ignora mayúsculas y espacios."""
    assert lookup(word, target) == expected


@pytest.mark.parametrize(
    ("valencian", "spanish"),
    [
        ("gos", "perro"),
        ("dels", "de los"),
        ("menuda", "pequeña"),
        ("rossa", "roja"),
        ("parc", "parque"),
        ("hui", "hoy"),
    ],
)
def test_entries_are_not_reversed(valencian: str, spanish: str) -> None:
    """Cada par va en el orden (castellano, valenciano), nunca al revés.

    Revertir un par produce un fallo silencioso: la palabra simplemente no se
    encuentra, sin ningún error visible.
    """
    assert lookup(valencian, "es") == spanish
    assert lookup(spanish, "ca") == valencian


def test_lookup_returns_none_for_unknown_word() -> None:
    """Una palabra que no está en el diccionario no se inventa."""
    assert lookup("zapatillodinosaurio", "ca") is None


def test_dictionary_has_no_empty_entries() -> None:
    """No hay entradas vacías ni espacios sobrantes."""
    for spanish, valencian in WORD_PAIRS:
        assert spanish.strip() == spanish
        assert valencian.strip() == valencian
        assert spanish and valencian


def test_lookup_direct_respects_direction() -> None:
    """La búsqueda por par traduce en el sentido que se pide."""
    assert lookup_direct("perro", "gos", "ca") == "gos"
    assert lookup_direct("perro", "gos", "es") == "perro"
    assert lookup_direct("quimpla", "quimpla", "ca") is None


def test_index_is_not_empty() -> None:
    """El índice se ha construido correctamente."""
    assert len(INDEX) > 100


@pytest.mark.parametrize(
    "value",
    ["perro", "de los", "papallona", "ha estat", "aigua"],
)
def test_plausible_translations_are_accepted(value: str) -> None:
    """Se aceptan palabras y frases cortas."""
    assert is_plausible_translation(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "El castellano es una lengua, así que la frase hui ya está en español",
        '{"gota": "raíz"}',
        "",
        "   ",
        "una traducción absurdamente larga de más de veinticuatro caracteres",
    ],
)
def test_implausible_translations_are_rejected(value: str) -> None:
    """Se descartan respuestas que no son traducciones."""
    assert is_plausible_translation(value) is False


def test_single_word_of_the_wrong_meaning_passes_the_format_check() -> None:
    """Una palabra plausible pero equivocada no se detecta por formato.

    Limitación conocida: el filtro descarta la prosa, el JSON y los textos
    larguísimos, pero no puede saber si una palabra suelta es semánticamente
    correcta. Por eso el diccionario es el camino preferente y el modelo solo
    cubre palabras poco frecuentes.
    """
    assert is_plausible_translation("sustantivo") is True


async def test_dictionary_translates_without_calling_the_model() -> None:
    """Las palabras conocidas se traducen sin tocar el modelo."""
    model = RecordingModel()
    service = HybridTranslationService(model=model)

    result = await service.translate(["gos", "parc", "llum"], "ca", "es")

    assert [pair[1] for pair in result.pairs] == ["perro", "parque", "luz"]
    assert model.calls == []


async def test_unknown_words_go_to_the_model() -> None:
    """Solo las palabras desconocidas llegan al modelo."""
    model = RecordingModel({"zombi": "zombi"})
    service = HybridTranslationService(model=model)

    result = await service.translate(["gos", "zombi"], "ca", "es")

    assert dict(result.pairs) == {"gos": "perro", "zombi": "zombi"}
    assert model.calls == [["zombi"]]


async def test_bad_model_output_keeps_the_original_word() -> None:
    """Si el modelo devuelve algo con mal formato, se mantiene el original."""
    model = RecordingModel({"zombi": "El castellano es una lengua, no puedo"})
    service = HybridTranslationService(model=model)

    result = await service.translate(["zombi"], "ca", "es")

    assert result.pairs == (("zombi", "zombi"),)


async def test_repeated_model_output_is_discarded() -> None:
    """Si el modelo repite la misma palabra para todo, se descarta todo.

    Es el fallo real observado con Phi-4-mini, que respondía "sustantivo" a
    cualquier palabra.
    """
    model = RecordingModel(
        {
            "quedronte": "sustantivo",
            "zamburi": "sustantivo",
            "trufi": "sustantivo",
        }
    )
    service = HybridTranslationService(model=model)

    result = await service.translate(["quedronte", "zamburi", "trufi"], "ca", "es")

    assert [pair[1] for pair in result.pairs] == ["quedronte", "zamburi", "trufi"]


async def test_model_failure_is_silent() -> None:
    """Si el modelo falla, la traducción del diccionario sigue funcionando."""
    model = RecordingModel(fail_with=ServiceError("error.generic", 502, "x"))
    service = HybridTranslationService(model=model)

    result = await service.translate(["gos", "quedronte"], "ca", "es")

    assert dict(result.pairs) == {"gos": "perro", "quedronte": "quedronte"}


async def test_service_works_without_a_model() -> None:
    """Sin modelo configurado, el diccionario sigue funcionando."""
    service = HybridTranslationService(model=None)

    result = await service.translate(["perro"], "es", "ca")

    assert result.pairs == (("perro", "gos"),)


async def test_empty_word_list() -> None:
    """Sin palabras no hay trabajo que hacer."""
    service = HybridTranslationService()

    assert (await service.translate([], "es", "ca")).pairs == ()
