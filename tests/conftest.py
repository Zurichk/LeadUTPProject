"""Configuración compartida de las pruebas.

Se inyectan dobles de los servicios de Azure para que la suite no dependa de
la nube.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.container import ServiceContainer  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.errors import ServiceError  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.ocr.models import OcrResult, OcrWord  # noqa: E402
from app.services.profiles import ProfileService  # noqa: E402
from app.services.speech import (  # noqa: E402
    SpeechRecognitionResult,
    SpeechSynthesisResult,
)
from app.services.storage import InMemoryStorageService  # noqa: E402
from app.services.translation import TranslationResult  # noqa: E402

# Las pruebas NUNCA deben leer el archivo .env del desarrollador: contiene
# secretos y valores reales de Azure, y haría que los tests dependieran de tu
# entorno local. Se anula a nivel de clase para toda la sesión.
Settings.model_config["env_file"] = None

FAKE_SHEET_TEXT = "Mika té un gos rosa que es diu Nube i juga al parc"


class FakeOcr:
    """OCR de mentira que devuelve un texto fijo.

    Args:
        text: Texto que devuelve como si fuese la ficha.
        fail_with: Excepción a lanzar en lugar de devolver el texto.
    """

    def __init__(
        self,
        text: str = FAKE_SHEET_TEXT,
        fail_with: Exception | None = None,
    ) -> None:
        self.text = text
        self.fail_with = fail_with
        self.calls: list[str] = []

    async def read_image(self, image: bytes, *, filename: str) -> OcrResult:
        """Devuelve el texto predefinido.

        Args:
            image: Bytes de la imagen (no se usan).
            filename: Nombre de la imagen.

        Returns:
            Resultado con las palabras troceadas.

        Raises:
            Exception: La indicada en ``fail_with``, si se configuró.
        """
        self.calls.append(filename)
        if self.fail_with is not None:
            raise self.fail_with
        words = tuple(
            OcrWord(text=token, confidence=0.95) for token in self.text.split()
        )
        return OcrResult(text=self.text, words=words, provider="fake")


class FakeSpeech:
    """Voz de mentira: devuelve audio vacío y una transcripción fija."""

    def __init__(
        self, recognized: str = "Mika", fail_with: Exception | None = None
    ) -> None:
        self.recognized = recognized
        self.fail_with = fail_with
        self.synthesized: list[tuple[str, str]] = []

    async def synthesize(
        self,
        text: str,
        language: str,
        *,
        voice: str | None = None,
    ) -> SpeechSynthesisResult:
        """Devuelve un audio simulado.

        Args:
            text: Texto solicitado.
            language: Idioma solicitado.
            voice: Voz opcional.

        Returns:
            Resultado con audio simulado.

        Raises:
            ServiceError: Si se configuró ``fail_with``.
        """
        if self.fail_with is not None:
            raise self.fail_with
        self.synthesized.append((text, language))
        return SpeechSynthesisResult(audio=b"ID3-fake-audio", voice="fake")

    async def recognize(self, audio: bytes, language: str) -> SpeechRecognitionResult:
        """Devuelve una transcripción simulada.

        Args:
            audio: Audio recibido (no se usa).
            language: Idioma solicitado.

        Returns:
            Transcripción simulada.

        Raises:
            ServiceError: Si se configuró ``fail_with``.
        """
        if self.fail_with is not None:
            raise self.fail_with
        return SpeechRecognitionResult(text=self.recognized, confidence=0.9)


@pytest.fixture
def settings() -> Settings:
    """Ajustes de prueba, sin dependencias de Azure."""
    return Settings(
        environment="local",
        demo_mode=False,
        match_threshold=0.8,
        default_max_words=12,
        speech_region="westeurope",
    )


class FakeTranslation:
    """Traducción de mentira que devuelve el idioma de destino.

    Args:
        fail_with: Excepción a lanzar en lugar de traducir.
    """

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.calls: list[tuple[list[str], str, str]] = []

    async def translate(
        self,
        words: list[str],
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """Devuelve una traducción simulada.

        Args:
            words: Palabras a traducir.
            source_language: Idioma de partida.
            target_language: Idioma de destino.

        Returns:
            Resultado con las traducciones simuladas.

        Raises:
            Exception: La indicada en ``fail_with``, si se configuró.
        """
        self.calls.append((list(words), source_language, target_language))
        if self.fail_with is not None:
            raise self.fail_with
        suffix = "-ca" if target_language == "ca" else "-es"
        return TranslationResult(
            pairs=tuple((word, f"{word}{suffix}") for word in words)
        )


@pytest.fixture
def translation() -> FakeTranslation:
    """Doble del servicio de traducción."""
    return FakeTranslation()


@pytest.fixture
def ocr() -> FakeOcr:
    """Doble del servicio de OCR."""
    return FakeOcr()


@pytest.fixture
def speech() -> FakeSpeech:
    """Doble del servicio de voz."""
    return FakeSpeech()


@pytest.fixture
def container(
    settings: Settings,
    ocr: FakeOcr,
    speech: FakeSpeech,
    translation: FakeTranslation,
) -> ServiceContainer:
    """Contenedor de servicios con dobles en memoria."""
    storage = InMemoryStorageService()
    return ServiceContainer(
        settings=settings,
        ocr=ocr,
        speech=speech,
        storage=storage,
        profiles=ProfileService(storage, settings.profiles_blob_name),
        translation=translation,
        http_client=httpx.AsyncClient(),
    )


@pytest.fixture
def client(container: ServiceContainer) -> Iterator[TestClient]:
    """Cliente HTTP de prueba con el contenedor de servicios inyectado."""

    async def builder(_settings: Settings) -> ServiceContainer:
        return container

    app = create_app(container.settings, container_builder=builder)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def png_bytes() -> bytes:
    """Imagen PNG mínima válida."""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )


@pytest.fixture
def failing_ocr_error() -> ServiceError:
    """Error de servicio usado para probar el fallo del OCR."""
    return ServiceError("error.ocr_failed", status_code=502, code="vision_error")
