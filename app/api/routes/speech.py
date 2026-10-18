"""Servicios de voz: síntesis (TTS), reconocimiento (STT) y evaluación.

La síntesis se hace en el servidor con Azure AI Speech; el reconocimiento
puede venir del navegador (Web Speech API) o de este endpoint cuando el
navegador no lo soporta.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.api.dependencies import ContainerDep, LanguageDep
from app.core.errors import ServiceError, ValidationError
from app.core.i18n import Translator
from app.schemas.speech import (
    EvaluationRequest,
    EvaluationResponse,
    RecognitionResponse,
    TtsRequest,
)
from app.services.evaluation import evaluate_pronunciation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["speech"])


@router.post(
    "/tts",
    summary="Sintetiza la pronunciación de una palabra",
    response_class=Response,
    responses={200: {"content": {"audio/mpeg": {}}, "description": "Audio MP3"}},
)
async def synthesize_speech(
    payload: TtsRequest,
    container: ContainerDep,
) -> Response:
    """Genera el audio de una palabra con la voz del idioma indicado.

    Args:
        payload: Palabra, idioma y voz opcional.
        container: Contenedor de servicios.

    Returns:
        El audio MP3 con la pronunciación.

    Raises:
        ServiceError: Si el servicio de voz no está disponible.
    """
    settings = container.settings
    result = await container.speech.synthesize(
        payload.word, payload.language, voice=payload.voice
    )
    return Response(
        content=result.audio,
        media_type=result.content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Speech-Voice": result.voice
            or settings.speech_voices.get(payload.language, ""),
        },
    )


@router.post(
    "/recognize-speech",
    response_model=RecognitionResponse,
    summary="Reconoce el audio enviado por el micrófono",
)
async def recognize_speech(
    container: ContainerDep,
    file: Annotated[UploadFile, File(description="Audio WAV 16 kHz mono")],
    language: Annotated[str, Form()] = "es",
) -> RecognitionResponse:
    """Transcribe el audio de una palabra con Azure AI Speech.

    Args:
        container: Contenedor de servicios.
        file: Audio WAV PCM 16 kHz mono capturado por el navegador.
        language: Idioma esperado (``es`` o ``ca``).

    Returns:
        Texto reconocido y su confianza.

    Raises:
        ValidationError: Si el audio está vacío o tiene un formato no admitido.
        ServiceError: Si el servicio de voz no está disponible.
    """
    settings = container.settings
    content_type = (file.content_type or "audio/wav").lower()
    if content_type not in settings.allowed_audio_types:
        raise ValidationError(
            "error.file_type", status_code=415, code="unsupported_media_type"
        )
    max_audio_bytes = settings.max_upload_bytes
    audio = await file.read(max_audio_bytes + 1)
    if len(audio) > max_audio_bytes:
        raise ValidationError("error.file_size", status_code=413, code="file_too_large")
    if not audio:
        raise ValidationError("error.empty_audio", status_code=422, code="empty_audio")
    result = await container.speech.recognize(audio, language)
    if not result.text:
        raise ValidationError("error.empty_audio", status_code=422, code="empty_audio")
    return RecognitionResponse(
        text=result.text, confidence=result.confidence, language=language
    )


@router.post(
    "/evaluate-speech",
    response_model=EvaluationResponse,
    summary="Compara lo reconocido con la palabra esperada",
)
async def evaluate_speech(
    payload: EvaluationRequest,
    container: ContainerDep,
    language: LanguageDep,
) -> EvaluationResponse:
    """Evalúa la pronunciación y devuelve el mensaje de refuerzo traducido.

    Args:
        payload: Palabra esperada y texto reconocido.
        container: Contenedor de servicios.
        language: Idioma del mensaje.

    Returns:
        Resultado de la evaluación con el mensaje de refuerzo.

    Raises:
        ServiceError: Si la palabra esperada no se puede evaluar.
    """
    try:
        evaluation = evaluate_pronunciation(
            payload.expected_word,
            payload.spoken_text,
            threshold=container.settings.match_threshold,
        )
    except ValueError as exc:
        logger.info("Palabra esperada inválida: %s", exc)
        raise ServiceError(
            "error.generic", status_code=422, code="invalid_expected_word"
        ) from exc
    translator = Translator(language)
    return EvaluationResponse(
        correct=evaluation.correct,
        score=evaluation.score,
        message=translator.t(evaluation.feedback_key),
        feedback_key=evaluation.feedback_key,
        heard=evaluation.spoken,
    )
