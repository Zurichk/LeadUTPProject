"""Perfiles de lectura (nombre y avatar) sin autenticación complexa."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from app.api.dependencies import ContainerDep
from app.schemas.profiles import ProfileCreate, ProfileOut
from app.services.profiles import Profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get(
    "",
    response_model=list[ProfileOut],
    summary="Lista los perfiles de lectura",
)
async def list_profiles(container: ContainerDep) -> list[ProfileOut]:
    """Devuelve los perfiles disponibles.

    Args:
        container: Contenedor de servicios.

    Returns:
        Lista de perfiles; si no hay ninguno guardado, los perfiles por defecto.
    """
    profiles = await container.profiles.list_profiles()
    return [
        ProfileOut(
            id=profile.id,
            name=profile.name,
            avatar=profile.avatar,
            language=profile.language,
        )
        for profile in profiles
    ]


@router.post(
    "",
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un perfil de lectura",
)
async def create_profile(
    payload: ProfileCreate,
    container: ContainerDep,
) -> ProfileOut:
    """Crea y guarda un perfil nuevo.

    Args:
        payload: Nombre, avatar e idioma del perfil.
        container: Contenedor de servicios.

    Returns:
        El perfil creado.

    Raises:
        ValidationError: Si el nombre o el avatar no son válidos.
    """
    profile = await container.profiles.add_profile(
        name=payload.name, avatar=payload.avatar, language=payload.language
    )
    return ProfileOut(
        id=profile.id,
        name=profile.name,
        avatar=profile.avatar,
        language=profile.language,
    )


__all__ = ("Profile", "router")
