"""Subida y análisis de la foto de la ficha de lectura.

Flujo: validar la imagen → guardarla en Blob Storage → extraer el texto con
Azure AI Vision → seleccionar las palabras de lectura.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.api.dependencies import ContainerDep
from app.core.errors import ValidationError
from app.core.i18n import normalize_language
from app.core.media import resolve_image_content_type
from app.schemas.sheets import SheetResponse, WordItem
from app.services.ocr import extract_words

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sheets"])


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Lee el contenido del archivo respetando el tamaño máximo.

    Args:
        file: Archivo subido.
        max_bytes: Tope de tamaño en bytes.

    Returns:
        Bytes del archivo.

    Raises:
        ValidationError: Si el archivo supera el tamaño permitido.
    """
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValidationError("error.file_size", status_code=413, code="file_too_large")
    return content


@router.post(
    "/upload-sheet",
    response_model=SheetResponse,
    status_code=201,
    summary="Sube una ficha de lectura y devuelve sus palabras",
)
async def upload_sheet(
    container: ContainerDep,
    file: Annotated[UploadFile, File(description="Foto de la ficha")],
    language: Annotated[str, Form()] = "auto",
    max_words: Annotated[int | None, Form(ge=1, le=100)] = None,
) -> SheetResponse:
    """Guarda la foto de la ficha y extrae las palabras de lectura.

    Args:
        container: Contenedor de servicios.
        file: Imagen de la ficha (JPEG, PNG, WebP o BMP).
        language: ``auto`` para detectarlo o un código ``es``/``ca``.
        max_words: Número máximo de palabras a devolver.

    Returns:
        La ficha analizada con su lista de palabras.

    Raises:
        ValidationError: Si el tipo o el tamaño de la imagen no son válidos.
        ServiceError: Si el OCR o el almacenamiento fallan.
    """
    settings = container.settings
    content = await _read_limited(file, settings.max_upload_bytes)
    content_type = resolve_image_content_type(content, settings.allowed_image_types)
    if content_type is None:
        logger.warning("Tipo de imagen rechazado: declarado=%s", file.content_type)
        raise ValidationError(
            "error.file_type", status_code=415, code="unsupported_media_type"
        )

    blob_name = await container.storage.upload_image(
        content, filename=file.filename or "ficha.jpg", content_type=content_type
    )

    ocr_result = await container.ocr.read_image(
        content, filename=file.filename or "ficha.jpg"
    )
    resolved_language = (
        None
        if language in ("auto", "", None)
        else normalize_language(language, settings.default_language)
    )
    words = extract_words(
        ocr_result,
        language=resolved_language,
        min_length=settings.min_word_length,
        max_length=settings.max_word_length,
        min_confidence=settings.min_ocr_confidence,
        max_words=min(
            max_words or settings.default_max_words, settings.max_words_limit
        ),
    )
    logger.info(
        "Ficha %s analizada: %d palabras (idioma %s)",
        blob_name,
        len(words),
        resolved_language or "auto",
    )
    return SheetResponse(
        blob_name=blob_name,
        language=words[0].language if words else (resolved_language or "es"),
        words=[
            WordItem(text=word.text, language=word.language, confidence=word.confidence)
            for word in words
        ],
        text_length=len(ocr_result.text),
    )
