"""Traducción opcional de las palabras de la ficha con Azure AI Foundry.

Es una función opcional: si el modelo no está configurado responde ``503`` y
la interfaz sigue mostrando las palabras originales.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from app.api.dependencies import ContainerDep
from app.schemas.translation import (
    TranslationRequest,
    TranslationResponse,
    WordTranslation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["translation"])


@router.post(
    "/translate-words",
    response_model=TranslationResponse,
    status_code=status.HTTP_200_OK,
    summary="Traduce las palabras de la ficha al otro idioma",
)
async def translate_words(
    payload: TranslationRequest,
    container: ContainerDep,
) -> TranslationResponse:
    """Traduce una lista de palabras al idioma contrario.

    Args:
        payload: Palabras e idiomas de origen y destino.
        container: Contenedor de servicios.

    Returns:
        Pares (original, traducción).

    Raises:
        ServiceError: Si la traducción no está disponible o falla.
    """
    result = await container.translation.translate(
        list(payload.words),
        payload.source_language,
        payload.target_language,
    )
    logger.info(
        "Traducidas %d palabras a '%s' (caché: %s)",
        len(result.pairs),
        payload.target_language,
        result.from_cache,
    )
    return TranslationResponse(
        translations=[
            WordTranslation(word=word, translated=translated)
            for word, translated in result.pairs
        ],
        target_language=payload.target_language,
        from_cache=result.from_cache,
    )
