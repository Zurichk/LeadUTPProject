"""Vista principal: interfaz infantil de lectura.

Args:
    request: Petición HTTP en curso.
    container: Contenedor de servicios.
    language: Idioma resuelto para la petición.

Returns:
    Página HTML con la interfaz de lectura.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.dependencies import ContainerDep, LanguageDep
from app.core.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS, Translator
from app.schemas.profiles import ProfileOut
from app.services.profiles import ALLOWED_AVATARS
from app.templating import templates

router = APIRouter(tags=["pages"])

APP_VERSION = "1.0.0"


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(
    request: Request,
    container: ContainerDep,
    language: LanguageDep,
) -> HTMLResponse:
    """Renderiza la interfaz infantil de lectura.

    Args:
        request: Petición HTTP en curso.
        container: Contenedor de servicios.
        language: Idioma resuelto.

    Returns:
        La página principal renderizada.
    """
    settings = container.settings
    translator = Translator(language)
    profiles = await container.profiles.list_profiles()
    context = {
        "app_name": settings.app_name,
        "version": APP_VERSION,
        "t": translator.t,
        "i18n": TRANSLATIONS[translator.language],
        "language": translator.language,
        "supported_languages": SUPPORTED_LANGUAGES,
        "profiles": [
            ProfileOut(
                id=profile.id,
                name=profile.name,
                avatar=profile.avatar,
                language=profile.language,
            ).model_dump()
            for profile in profiles
        ],
        "avatars": ALLOWED_AVATARS,
        "default_max_words": settings.default_max_words,
        "max_upload_mb": settings.max_upload_mb,
        "demo_mode": settings.demo_mode,
        "speech_backend": settings.speech_backend,
        "letter_case": settings.letter_case,
        "translation_enabled": settings.translation_configured,
    }
    return templates.TemplateResponse(
        request=request, name="index.html", context=context
    )
