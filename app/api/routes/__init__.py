"""Routers de la aplicación.

Se agrupan aquí para montarlos todos desde :func:`app.main.create_app`.
"""

from __future__ import annotations

from app.api.routes.health import router as health_router
from app.api.routes.pages import router as pages_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.sheets import router as sheets_router
from app.api.routes.speech import router as speech_router
from app.api.routes.translation import router as translation_router

ALL_ROUTERS = (
    health_router,
    pages_router,
    sheets_router,
    speech_router,
    profiles_router,
    translation_router,
)

__all__ = ("ALL_ROUTERS",)
