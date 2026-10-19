"""Configuración tipada de la aplicación mediante variables de entorno.

Todas las claves se leen con el prefijo ``LECTURA_`` y admiten un archivo
``.env`` en la raíz del proyecto (útil para desarrollo local). En Azure la
inyección se hace mediante la Managed Identity del App Service, por lo que no
es necesario definir claves de API cuando se usan identidades administradas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

LanguageCode = Literal["es", "ca"]
Environment = Literal["local", "dev", "prod"]
OcrProvider = Literal["vision", "document_intelligence"]
SpeechBackend = Literal["auto", "browser", "azure"]
LetterCase = Literal["upper", "lower", "both"]

#: Ámbito del token AAD para los servicios de Azure AI (Vision, Document
#: Intelligence y Speech).
AZURE_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"

#: Voz neuronal por defecto para cada idioma soportado.
DEFAULT_VOICES: dict[str, str] = {
    "es": "es-ES-ElviraNeural",
    "ca": "ca-ES-JoanaNeural",
}


class Settings(BaseSettings):
    """Ajustes de la aplicación.

    Attributes:
        app_name: Nombre visible de la aplicación.
        environment: Entorno de ejecución.
        log_level: Nivel de logging (``DEBUG``, ``INFO``…).
        supported_languages: Idiomas soportados por la interfaz.
        default_language: Idioma usado si el usuario no elige otro.
        max_upload_mb: Tamaño máximo de la foto de la ficha.
        allowed_image_types: Tipos MIME aceptados para la foto.
        allowed_audio_types: Tipos MIME aceptados para el audio del micrófono.
        min_word_length: Longitud mínima de una palabra extraída del OCR.
        max_word_length: Longitud máxima de una palabra extraída del OCR.
        default_max_words: Número de tarjetas por defecto.
        max_words_limit: Tope duro de tarjetas por ficha.
        min_ocr_confidence: Confianza mínima del OCR para aceptar una palabra.
        match_threshold: Similitud mínima (0-1) para considerar buena la
            pronunciación.
        demo_mode: Activa el modo demostración sin credenciales de Azure.
        letter_case: Cómo se muestran las palabras en las tarjetas: ``upper``,
            ``lower`` o ``both`` (mayúscula grande y minúscula debajo).
        blob_container: Contenedor donde se guardan las fotos.
        blob_service_url: URL del recurso de Blob Storage (identidad
            administrada).
        blob_connection_string: Cadena de conexión (solo desarrollo local).
        profiles_blob_name: Nombre del blob con los perfiles de usuario.
        ocr_provider: Proveedor de OCR a utilizar.
        vision_endpoint: Endpoint del recurso de Azure AI Vision.
        vision_key: Clave de Vision (solo local; en Azure se usa la identidad).
        document_intelligence_endpoint: Endpoint de Document Intelligence.
        document_intelligence_key: Clave de Document Intelligence (solo local).
        speech_region: Región del recurso de Azure AI Speech.
        speech_key: Clave de Speech (solo desarrollo local; en Azure se usa la
            Managed Identity).
        speech_backend: Motor de voz: ``auto`` (intenta Azure y cae al
            navegador), ``browser`` (solo Web Speech API) o ``azure``.
        speech_voices: Voz neuronal por idioma.
        max_ocr_wait_seconds: Tiempo máximo de espera del análisis asíncrono de
            Document Intelligence.
        tts_cache_size: Número máximo de audios sintetizados en memoria.
        translation_enabled: Activa la traducción con un modelo de Foundry.
        foundry_endpoint: Base URL de inferencia
            (``https://<cuenta>.openai.azure.com/openai/v1``).
        foundry_deployment: Nombre del deployment del modelo.
        foundry_api_key: Clave de Foundry (solo local; en Azure se usa la
            Managed Identity).
        foundry_timeout_seconds: Espera máxima al modelo de traducción.
        translation_cache_size: Traducciones guardadas en memoria.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LECTURA_",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "LecturaFácil"
    environment: Environment = "local"
    log_level: str = "INFO"
    debug: bool = False

    supported_languages: tuple[LanguageCode, ...] = ("es", "ca")
    default_language: LanguageCode = "es"

    max_upload_mb: int = Field(default=12, ge=1, le=50)
    allowed_image_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/bmp",
    )
    allowed_audio_types: tuple[str, ...] = (
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/vnd.wave",
        "application/octet-stream",
    )

    min_word_length: int = Field(default=2, ge=1, le=10)
    max_word_length: int = Field(default=15, ge=4, le=40)
    default_max_words: int = Field(default=12, ge=1, le=50)
    max_words_limit: int = Field(default=30, ge=1, le=100)
    min_ocr_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    match_threshold: float = Field(default=0.72, ge=0.0, le=1.0)

    demo_mode: bool = False
    letter_case: LetterCase = "both"

    blob_container: str = "fichas-lectura"
    blob_service_url: str | None = None
    blob_connection_string: str | None = None
    profiles_blob_name: str = "perfiles.json"

    ocr_provider: OcrProvider = "vision"
    vision_endpoint: str | None = None
    vision_api_version: str = "2024-02-01"
    vision_key: str | None = None
    document_intelligence_endpoint: str | None = None
    document_intelligence_api_version: str = "2024-11-30"
    document_intelligence_key: str | None = None

    # Traducción opcional con un modelo de Azure AI Foundry.
    translation_enabled: bool = False
    foundry_endpoint: str | None = None
    foundry_deployment: str = "Phi-4-mini-instruct"
    foundry_api_key: str | None = None
    foundry_timeout_seconds: float = Field(default=12.0, gt=0)
    translation_cache_size: int = Field(default=512, ge=0)

    speech_region: str = "westeurope"
    speech_key: str | None = None
    speech_backend: SpeechBackend = "auto"
    speech_voices: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_VOICES))
    max_ocr_wait_seconds: float = Field(default=60.0, gt=0)
    tts_cache_size: int = Field(default=256, ge=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_upload_bytes(self) -> int:
        """Tamaño máximo de la foto expresado en bytes."""
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """Indica si la aplicación se ejecuta en producción."""
        return self.environment == "prod"

    def missing_services(self) -> list[str]:
        """Devuelve los servicios de Azure que faltan por configurar.

        Returns:
            Lista de nombres legibles de ajustes ausentes. Vacía si la
            configuración es válida o si está activo el modo demostración.
        """
        missing: list[str] = []
        if not self.storage_configured:
            missing.append("blob_service_url o blob_connection_string")
        if not self.ocr_configured:
            missing.append(f"endpoint de OCR ({self.ocr_provider})")
        if not self.speech_configured:
            missing.append("speech_region")
        return missing

    @property
    def storage_configured(self) -> bool:
        """Indica si hay configuración suficiente para Blob Storage."""
        return bool(self.blob_service_url or self.blob_connection_string)

    @property
    def ocr_configured(self) -> bool:
        """Indica si hay endpoint configurado para el proveedor de OCR."""
        if self.ocr_provider == "vision":
            return bool(self.vision_endpoint)
        return bool(self.document_intelligence_endpoint)

    @property
    def speech_configured(self) -> bool:
        """Indica si el servicio de voz puede resolverse.

        En Azure basta con la región (token de la Managed Identity); en local
        se puede usar una clave estática opcional.
        """
        return bool(self.speech_region)

    @property
    def translation_configured(self) -> bool:
        """Indica si la traducción con Foundry está disponible."""
        return bool(self.translation_enabled and self.foundry_endpoint)
