"""Perfiles de usuario sencillos (nombre + avatar) sin contraseñas.

Los perfiles se guardan como un pequeño JSON en Blob Storage, lo que evita
montar una base de datos para un uso familiar muy simple.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.errors import ValidationError
from app.core.i18n import normalize_language
from app.services.storage import MAX_PROFILES, StoragePort

logger = logging.getLogger(__name__)

#: Avatares permitidos (emoji). Lista cerrada para evitar contenido inesperado.
ALLOWED_AVATARS: tuple[str, ...] = (
    "👧",
    "👦",
    "🦄",
    "🐻",
    "🐱",
    "🐶",
    "🦊",
    "🐰",
    "🦁",
    "🐨",
    "🐧",
    "🦖",
)


@dataclass(frozen=True, slots=True)
class Profile:
    """Perfil de lectura.

    Attributes:
        id: Identificador estable generado por el servidor.
        name: Nombre corto del niño o niña.
        avatar: Emoji del avatar.
        language: Idioma preferido (``"es"`` o ``"ca"``).
    """

    id: str
    name: str
    avatar: str
    language: str = "es"


DEFAULT_PROFILES: tuple[Profile, ...] = (
    Profile(id="mika", name="Mika", avatar="👧", language="es"),
    Profile(id="pau", name="Pau", avatar="👦", language="ca"),
)


def _profile_from_dict(payload: dict[str, Any]) -> Profile | None:
    """Construye un perfil desde su representación en el blob.

    Args:
        payload: Diccionario con los campos del perfil.

    Returns:
        Perfil válido o ``None`` si los datos son insuficientes.
    """
    name = str(payload.get("name", "")).strip()
    if not name:
        return None
    avatar = str(payload.get("avatar", ALLOWED_AVATARS[0]))
    if avatar not in ALLOWED_AVATARS:
        avatar = ALLOWED_AVATARS[0]
    return Profile(
        id=str(payload.get("id") or uuid.uuid4().hex[:8]),
        name=name[:24],
        avatar=avatar,
        language=normalize_language(str(payload.get("language", "es"))),
    )


def _profile_to_dict(profile: Profile) -> dict[str, str]:
    """Serializa un perfil para guardarlo en el blob.

    Args:
        profile: Perfil a serializar.

    Returns:
        Diccionario con los campos del perfil.
    """
    return {
        "id": profile.id,
        "name": profile.name,
        "avatar": profile.avatar,
        "language": profile.language,
    }


class ProfileService:
    """Gestiona los perfiles de lectura almacenados en Blob Storage.

    Args:
        storage: Puerto de almacenamiento.
        blob_name: Nombre del blob con la lista de perfiles.
    """

    def __init__(self, storage: StoragePort, blob_name: str = "perfiles.json") -> None:
        self._storage = storage
        self._blob_name = blob_name

    async def list_profiles(self) -> list[Profile]:
        """Devuelve los perfiles guardados.

        Returns:
            Lista de perfiles; si no hay datos, los perfiles por defecto.
        """
        payload = await self._storage.read_json(self._blob_name)
        if not payload:
            return list(DEFAULT_PROFILES)
        raw_profiles = payload.get("profiles")
        if not isinstance(raw_profiles, list):
            return list(DEFAULT_PROFILES)
        profiles = [
            profile
            for item in raw_profiles
            if isinstance(item, dict)
            if (profile := _profile_from_dict(item)) is not None
        ]
        return profiles or list(DEFAULT_PROFILES)

    async def add_profile(
        self,
        name: str,
        avatar: str,
        language: str = "es",
    ) -> Profile:
        """Crea y guarda un perfil nuevo.

        Args:
            name: Nombre del perfil (1-24 caracteres).
            avatar: Emoji del avatar (debe estar en :data:`ALLOWED_AVATARS`).
            language: Idioma preferido.

        Returns:
            El perfil creado y ya persistido.

        Raises:
            ValidationError: Si el nombre o el avatar no son válidos, o si se
                supera el máximo de perfiles.
        """
        clean_name = " ".join(name.split())
        if not clean_name or len(clean_name) > 24:
            raise ValidationError(
                "error.generic", status_code=422, code="invalid_profile_name"
            )
        if avatar not in ALLOWED_AVATARS:
            raise ValidationError(
                "error.generic", status_code=422, code="invalid_profile_avatar"
            )
        profiles = await self.list_profiles()
        if len(profiles) >= MAX_PROFILES:
            raise ValidationError(
                "error.generic", status_code=409, code="too_many_profiles"
            )
        profile = Profile(
            id=uuid.uuid4().hex[:8],
            name=clean_name,
            avatar=avatar,
            language=normalize_language(language),
        )
        profiles.append(profile)
        await self._storage.write_json(
            self._blob_name, {"profiles": [_profile_to_dict(p) for p in profiles]}
        )
        logger.info("Perfil creado: %s", profile.id)
        return profile
