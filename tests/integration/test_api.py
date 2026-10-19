"""Pruebas de integración de la API HTTP."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.container import ServiceContainer
from app.core.config import Settings
from app.core.errors import ServiceError
from app.main import create_app
from app.services.profiles import ProfileService
from app.services.speech import UnavailableSpeechService
from app.services.storage import InMemoryStorageService
from app.services.translation import UnavailableTranslationService
from tests.conftest import FakeOcr, FakeSpeech


def test_home_renders_kids_interface(client: TestClient) -> None:
    """La página principal se renderiza en castellano."""
    response = client.get("/")

    assert response.status_code == 200
    assert 'lang="es"' in response.text
    assert "LecturaFácil" in response.text
    assert "/static/css/kids.css" in response.text


def test_health_reports_the_services(client: TestClient) -> None:
    """El sondeo de salud responde e informa sin revelar secretos."""
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "LecturaFácil"
    assert set(payload["services"]) == {
        "ocr",
        "storage",
        "speech",
        "translation",
        "demo_mode",
    }


def test_health_alias_under_api(client: TestClient) -> None:
    """También existe /api/health para sondeos que usan ese prefijo."""
    assert client.get("/api/health").status_code == 200


def test_recognize_speech_reports_503_when_voice_is_browser_only() -> None:
    """Sin Azure Speech el reconocimiento del servidor responde 503."""
    settings = Settings(speech_backend="browser")
    storage = InMemoryStorageService()
    container = ServiceContainer(
        settings=settings,
        ocr=FakeOcr(),
        speech=UnavailableSpeechService(),
        storage=storage,
        profiles=ProfileService(storage, settings.profiles_blob_name),
        translation=UnavailableTranslationService(),
        http_client=httpx.AsyncClient(),
    )

    async def builder(_: Settings) -> ServiceContainer:
        return container

    app = create_app(settings, container_builder=builder)
    with TestClient(app) as browser_client:
        response = browser_client.post(
            "/api/recognize-speech",
            files={"file": ("audio.wav", b"RIFF-fake", "audio/wav")},
            data={"language": "es"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "speech_not_configured"


def test_home_renders_in_valencian(client: TestClient) -> None:
    """Con ``?lang=ca`` la interfaz se muestra en valenciano."""
    response = client.get("/", params={"lang": "ca"})

    assert response.status_code == 200
    assert 'lang="ca"' in response.text
    assert "Anem a llegir junts" in response.text


def test_home_exposes_the_voice_backend(client: TestClient) -> None:
    """La interfaz conoce qué motor de voz debe usar."""
    response = client.get("/")

    assert 'speechBackend: "auto"' in response.text


def test_home_exposes_the_letter_case_selector(client: TestClient) -> None:
    """La interfaz ofrece los tres modos de letras."""
    response = client.get("/")

    assert 'letterCase: "both"' in response.text
    for mode in ("upper", "lower", "both"):
        assert f'data-case="{mode}"' in response.text


def test_home_renders_browser_only_mode() -> None:
    """En modo navegador la interfaz no intenta llamar a Azure."""
    settings = Settings(speech_backend="browser")
    storage = InMemoryStorageService()
    container = ServiceContainer(
        settings=settings,
        ocr=FakeOcr(),
        speech=UnavailableSpeechService(),
        storage=storage,
        profiles=ProfileService(storage, settings.profiles_blob_name),
        translation=UnavailableTranslationService(),
        http_client=httpx.AsyncClient(),
    )

    async def builder(_: Settings) -> ServiceContainer:
        return container

    app = create_app(settings, container_builder=builder)
    with TestClient(app) as browser_client:
        response = browser_client.get("/")
        tts = browser_client.post("/api/tts", json={"word": "gos", "language": "ca"})

    assert 'speechBackend: "browser"' in response.text
    assert tts.status_code == 503
    assert tts.json()["error"]["code"] == "speech_not_configured"


def test_upload_sheet_returns_words(client: TestClient, png_bytes: bytes) -> None:
    """La ficha se guarda y devuelve las palabras detectadas."""
    response = client.post(
        "/api/upload-sheet",
        files={"file": ("ficha.png", png_bytes, "image/png")},
        data={"language": "auto", "max_words": "5"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["blob_name"].startswith("fichas/")
    assert 0 < len(payload["words"]) <= 5
    assert all(word["language"] in {"es", "ca"} for word in payload["words"])


def test_upload_sheet_stores_the_image(
    client: TestClient, png_bytes: bytes, ocr: FakeOcr
) -> None:
    """La imagen se envía al almacenamiento antes de analizarse."""
    client.post(
        "/api/upload-sheet",
        files={"file": ("ficha.png", png_bytes, "image/png")},
    )

    assert ocr.calls == ["ficha.png"]


def test_upload_sheet_rejects_non_images(client: TestClient) -> None:
    """Un archivo que no es imagen se rechaza."""
    response = client.post(
        "/api/upload-sheet",
        files={"file": ("notas.txt", b"hola", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_upload_sheet_accepts_generic_content_type(
    client: TestClient, png_bytes: bytes
) -> None:
    """Si el navegador no indica el tipo, se valida por contenido."""
    response = client.post(
        "/api/upload-sheet",
        files={"file": ("ficha.png", png_bytes, "application/octet-stream")},
    )

    assert response.status_code == 201
    assert response.json()["blob_name"].endswith(".png")


def test_upload_sheet_rejects_fake_image(client: TestClient) -> None:
    """Un archivo de texto con extensión de imagen se rechaza."""
    response = client.post(
        "/api/upload-sheet",
        files={"file": ("ficha.jpg", b"esto no es una imagen", "image/jpeg")},
    )

    assert response.status_code == 415


def test_upload_sheet_reports_ocr_failure(
    client: TestClient,
    png_bytes: bytes,
    ocr: FakeOcr,
    failing_ocr_error: ServiceError,
) -> None:
    """Un fallo del OCR se traduce a un error de servicio."""
    ocr.fail_with = failing_ocr_error

    response = client.post(
        "/api/upload-sheet",
        files={"file": ("ficha.png", png_bytes, "image/png")},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "vision_error"


def test_tts_returns_audio(client: TestClient, speech: FakeSpeech) -> None:
    """La síntesis devuelve audio con la voz del idioma."""
    response = client.post("/api/tts", json={"word": "mariposa", "language": "es"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content
    assert speech.synthesized == [("mariposa", "es")]


def test_tts_rejects_dangerous_text(client: TestClient) -> None:
    """No se sintetiza texto con caracteres de marcado."""
    response = client.post("/api/tts", json={"word": "<script>", "language": "es"})

    assert response.status_code == 422


def test_recognize_speech_returns_text(client: TestClient) -> None:
    """El reconocedor devuelve la transcripción simulada."""
    response = client.post(
        "/api/recognize-speech",
        files={"file": ("audio.wav", b"RIFF-fake", "audio/wav")},
        data={"language": "es"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "Mika",
        "confidence": 0.9,
        "language": "es",
    }


def test_recognize_speech_rejects_empty_audio(client: TestClient) -> None:
    """Un audio vacío se rechaza."""
    response = client.post(
        "/api/recognize-speech",
        files={"file": ("audio.wav", b"", "audio/wav")},
        data={"language": "es"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_audio"


def test_evaluate_speech_correct(client: TestClient) -> None:
    """Una pronunciación correcta devuelve el elogio en castellano."""
    response = client.post(
        "/api/evaluate-speech",
        json={
            "expected_word": "mariposa",
            "spoken_text": "Mariposa!",
            "language": "es",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["correct"] is True
    assert payload["message"] == "¡Muy bien!"


def test_evaluate_speech_in_valencian(client: TestClient) -> None:
    """El mensaje de refuerzo sigue el idioma del navegador."""
    response = client.post(
        "/api/evaluate-speech?lang=ca",
        json={"expected_word": "gos", "spoken_text": "gos", "language": "ca"},
    )

    assert response.json()["message"] == "Molt bé!"


def test_evaluate_speech_wrong_word(client: TestClient) -> None:
    """Una palabra incorrecta no se da por buena."""
    response = client.post(
        "/api/evaluate-speech",
        json={"expected_word": "mariposa", "spoken_text": "perro", "language": "es"},
    )

    payload = response.json()
    assert payload["correct"] is False
    assert payload["score"] < 0.5


@pytest.mark.parametrize(
    ("payload_body", "expected_status"),
    [
        ({"expected_word": "", "spoken_text": "hola"}, 422),
        ({"expected_word": "gos", "spoken_text": "x" * 500}, 422),
    ],
)
def test_evaluate_speech_validates_input(
    client: TestClient, payload_body: dict[str, str], expected_status: int
) -> None:
    """Los datos inválidos devuelven 422."""
    response = client.post("/api/evaluate-speech", json=payload_body)

    assert response.status_code == expected_status


def test_list_profiles_returns_defaults(client: TestClient) -> None:
    """Se devuelven los perfiles por defecto."""
    response = client.get("/api/profiles")

    assert response.status_code == 200
    assert [profile["name"] for profile in response.json()] == ["Mika", "Pau"]


def test_create_profile(client: TestClient) -> None:
    """Se puede crear un perfil nuevo."""
    response = client.post(
        "/api/profiles",
        json={"name": "Lucía", "avatar": "🦄", "language": "ca"},
    )

    assert response.status_code == 201
    assert response.json()["avatar"] == "🦄"
    assert len(client.get("/api/profiles").json()) == 3


def test_create_profile_rejects_unknown_avatar(client: TestClient) -> None:
    """Un avatar no permitido se rechaza."""
    response = client.post(
        "/api/profiles", json={"name": "Ana", "avatar": "ninja", "language": "es"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_profile_avatar"
