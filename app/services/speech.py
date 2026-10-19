"""Azure AI Speech: síntesis de voz (TTS) y reconocimiento (STT).

Se usa la API REST con autenticación por Managed Identity, que evita depender
del SDK nativo y funciona igual en App Service y en local. El navegador usa
además la Web Speech API como camino rápido y usa este servicio como respaldo.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol
from xml.sax.saxutils import escape

import httpx

from app.core.auth import CognitiveAuth
from app.core.config import Settings
from app.core.errors import ServiceError
from app.core.i18n import normalize_language

logger = logging.getLogger(__name__)

#: Locuciones de Azure Speech associate al idioma de la tarjeta.
LOCALE_BY_LANGUAGE: dict[str, str] = {"es": "es-ES", "ca": "ca-ES"}

#: Formato de audio de salida de la síntesis.
TTS_AUDIO_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
TTS_CONTENT_TYPE = "audio/mpeg"
STT_CONTENT_TYPE = "audio/wav; codecs=audio/pcm; samplerate=16000"


@dataclass(frozen=True, slots=True)
class SpeechSynthesisResult:
    """Audio sintetizado de una palabra.

    Attributes:
        audio: Bytes del audio en MP3.
        content_type: Tipo MIME del audio.
        voice: Voz neuronal utilizada.
    """

    audio: bytes
    content_type: str = TTS_CONTENT_TYPE
    voice: str = ""


@dataclass(frozen=True, slots=True)
class SpeechRecognitionResult:
    """Transcripción del audio del micrófono.

    Attributes:
        text: Texto reconocido (puede estar vacío).
        confidence: Confianza del reconocedor entre 0 y 1.
    """

    text: str
    confidence: float = 0.0


class SpeechPort(Protocol):
    """Contrato del servicio de voz."""

    async def synthesize(
        self,
        text: str,
        language: str,
        *,
        voice: str | None = None,
    ) -> SpeechSynthesisResult:
        """Sintetiza una palabra.

        Args:
            text: Texto a pronunciar.
            language: Idioma (``"es"`` o ``"ca"``).
            voice: Voz neuronal a forzar (opcional).

        Returns:
            Audio MP3 de la palabra.
        """
        ...

    async def recognize(self, audio: bytes, language: str) -> SpeechRecognitionResult:
        """Reconoce el audio de una palabra.

        Args:
            audio: Audio WAV PCM 16 kHz mono.
            language: Idioma esperado.

        Returns:
            Texto reconocido y su confianza.
        """
        ...


def build_ssml(text: str, voice: str, locale: str) -> str:
    """Construye la petición SSML para la síntesis de voz.

    Args:
        text: Texto a pronunciar (se escapa como XML).
        voice: Nombre de la voz neuronal.
        locale: Locución (p. ej. ``es-ES``).

    Returns:
        Documento SSML listo para enviar al servicio.
    """
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'"
        f" xml:lang='{escape(locale)}'>"
        f"<voice xml:lang='{escape(locale)}' name='{escape(voice)}'>"
        f"{escape(text)}"
        "</voice></speak>"
    )


class AzureSpeechService:
    """Adaptador de Azure AI Speech (REST).

    Args:
        settings: Ajustes de la aplicación.
        auth: Proveedor de cabeceras de autenticación.
        client: Cliente HTTP asíncrono compartido.
    """

    def __init__(
        self,
        settings: Settings,
        auth: CognitiveAuth,
        client: httpx.AsyncClient,
    ) -> None:
        self._settings = settings
        self._auth = auth
        self._client = client
        self._cache: OrderedDict[tuple[str, str], SpeechSynthesisResult] = OrderedDict()

    def _voice_for(self, language: str, voice: str | None) -> str:
        """Resuelve la voz neuronal a utilizar.

        Args:
            language: Idioma normalizado.
            voice: Voz forzada opcional.

        Returns:
            Nombre de la voz.
        """
        return voice or self._settings.speech_voices.get(language, "es-ES-ElviraNeural")

    async def synthesize(
        self,
        text: str,
        language: str,
        *,
        voice: str | None = None,
    ) -> SpeechSynthesisResult:
        """Sintetiza una palabra usando la voz del idioma indicado.

        Args:
            text: Palabra a pronunciar.
            language: Idioma (``"es"`` o ``"ca"``).
            voice: Voz neuronal opcional.

        Returns:
            Resultado con el audio MP3.

        Raises:
            ServiceError: Si el servicio devuelve un error o un audio vacío.
        """
        resolved_language = normalize_language(
            language, self._settings.default_language
        )
        locale = LOCALE_BY_LANGUAGE.get(resolved_language, "es-ES")
        selected_voice = self._voice_for(resolved_language, voice)
        cache_key = (text, selected_voice)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return cached

        url = (
            f"https://{self._settings.speech_region}.tts.speech.microsoft.com"
            "/cognitiveservices/v1"
        )
        headers = {
            **await self._auth.headers(),
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": TTS_AUDIO_FORMAT,
            "User-Agent": "LecturaFacil/1.0",
        }
        response = await self._client.post(
            url,
            content=build_ssml(text, selected_voice, locale).encode("utf-8"),
            headers=headers,
        )
        if response.status_code >= 400 or not response.content:
            logger.error("Azure TTS respondió %s para '%s'", response.status_code, text)
            raise ServiceError("error.generic", status_code=502, code="tts_error")
        result = SpeechSynthesisResult(audio=response.content, voice=selected_voice)
        self._cache[cache_key] = result
        while len(self._cache) > max(self._settings.tts_cache_size, 0):
            self._cache.popitem(last=False)
        return result

    async def recognize(self, audio: bytes, language: str) -> SpeechRecognitionResult:
        """Transcribe el audio enviado por el micrófono.

        Args:
            audio: Audio WAV PCM 16 kHz mono.
            language: Idioma esperado.

        Returns:
            Texto reconocido y confianza.

        Raises:
            ServiceError: Si el servicio devuelve un error.
        """
        resolved_language = normalize_language(
            language, self._settings.default_language
        )
        locale = LOCALE_BY_LANGUAGE.get(resolved_language, "es-ES")
        url = (
            f"https://{self._settings.speech_region}.stt.speech.microsoft.com"
            "/speech/recognition/conversation/cognitiveservices/v1"
            f"?language={locale}&format=detailed"
        )
        headers = {
            **await self._auth.headers(),
            "Content-Type": STT_CONTENT_TYPE,
            "Accept": "application/json",
            "User-Agent": "LecturaFacil/1.0",
        }
        response = await self._client.post(url, content=audio, headers=headers)
        if response.status_code >= 400:
            logger.error("Azure STT respondió %s", response.status_code)
            raise ServiceError("error.generic", status_code=502, code="stt_error")
        return _parse_recognition(response.json())


def _parse_recognition(payload: dict[str, object]) -> SpeechRecognitionResult:
    """Extrae el texto reconocido de la respuesta de Azure STT.

    Args:
        payload: Cuerpo JSON de la respuesta.

    Returns:
        Texto de la mejor hipótesis y su confianza.
    """
    status = str(payload.get("RecognitionStatus", ""))
    if status != "Success":
        logger.info("Azure STT devolvió el estado %s", status or "desconocido")
        return SpeechRecognitionResult(text="", confidence=0.0)
    candidates = payload.get("NBest")
    best: dict[str, object] = {}
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            best = first
    text = str(best.get("DisplayText") or payload.get("DisplayText") or "").strip()
    raw_confidence = best.get("Confidence")
    confidence = (
        float(raw_confidence) if isinstance(raw_confidence, int | float) else 0.0
    )
    return SpeechRecognitionResult(text=text, confidence=confidence)


class UnavailableSpeechService:
    """Servicio de voz no disponible (modo demostración o sin credenciales).

    Permite que la aplicación arranque y que el frontend recurra a la Web
    Speech API del navegador.
    """

    async def synthesize(
        self,
        text: str,
        language: str,
        *,
        voice: str | None = None,
    ) -> SpeechSynthesisResult:
        """Indica que la síntesis en servidor no está disponible.

        Raises:
            ServiceError: Siempre, con código ``speech_not_configured``.
        """
        raise ServiceError(
            "error.not_configured",
            status_code=503,
            code="speech_not_configured",
            service="Azure AI Speech",
        )

    async def recognize(self, audio: bytes, language: str) -> SpeechRecognitionResult:
        """Indica que el reconocimiento en servidor no está disponible.

        Args:
            audio: Audio recibido (no se procesa).
            language: Idioma solicitado (no se usa).

        Raises:
            ServiceError: Siempre, con código ``speech_not_configured``.
        """
        raise ServiceError(
            "error.not_configured",
            status_code=503,
            code="speech_not_configured",
            service="Azure AI Speech",
        )
