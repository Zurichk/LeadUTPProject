"""Pruebas de almacenamiento en memoria, sanitización y perfiles."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.services.profiles import ALLOWED_AVATARS, ProfileService
from app.services.storage import (
    InMemoryStorageService,
    build_blob_name,
    sanitize_filename,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("../../etc/passwd.jpg", "passwd.jpg"),
        ("ficha de lectura.png", "ficha-de-lectura.png"),
        ("", "ficha.jpg"),
        ("ficha 2024 (1).jpg", "ficha-2024-1-.jpg"),
    ],
)
def test_sanitize_filename(filename: str, expected: str) -> None:
    """Se eliminan rutas y caracteres peligrosos del nombre."""
    assert sanitize_filename(filename) == expected


def test_build_blob_name_is_unique() -> None:
    """Dos subidas generan nombres distintos con la misma extensión."""
    first = build_blob_name("ficha.jpg")
    second = build_blob_name("ficha.jpg")

    assert first.startswith("fichas/")
    assert first.endswith(".jpg")
    assert first != second


async def test_in_memory_storage_roundtrip() -> None:
    """El almacenamiento en memoria guarda y devuelve JSON."""
    storage = InMemoryStorageService()

    await storage.write_json("perfiles.json", {"profiles": []})
    assert await storage.read_json("perfiles.json") == {"profiles": []}
    assert await storage.read_json("no-existe.json") is None


async def test_in_memory_storage_upload() -> None:
    """La imagen se guarda y devuelve un nombre de blob."""
    storage = InMemoryStorageService()

    name = await storage.upload_image(
        b"abc", filename="ficha.png", content_type="image/png"
    )

    assert name.startswith("fichas/")
    assert name.endswith(".png")


async def test_default_profiles_when_empty() -> None:
    """Sin datos guardados se devuelven los perfiles por defecto."""
    service = ProfileService(InMemoryStorageService())

    profiles = await service.list_profiles()

    assert [profile.name for profile in profiles] == ["Mika", "Pau"]


async def test_add_profile_persists() -> None:
    """El perfil nuevo se guarda y aparece en la lista."""
    storage = InMemoryStorageService()
    service = ProfileService(storage)

    created = await service.add_profile("Lucía", "🦄", "ca")

    assert created.avatar in ALLOWED_AVATARS
    assert [profile.name for profile in await service.list_profiles()] == [
        "Mika",
        "Pau",
        "Lucía",
    ]


async def test_add_profile_rejects_unknown_avatar() -> None:
    """Un avatar fuera de la lista se rechaza."""
    service = ProfileService(InMemoryStorageService())

    with pytest.raises(ValidationError):
        await service.add_profile("Pep", "<script>", "es")


async def test_add_profile_rejects_empty_name() -> None:
    """Un nombre vacío se rechaza."""
    service = ProfileService(InMemoryStorageService())

    with pytest.raises(ValidationError):
        await service.add_profile("   ", ALLOWED_AVATARS[0], "es")


async def test_invalid_stored_profile_is_skipped() -> None:
    """Los registros corruptos del blob se ignoran al leer."""
    storage = InMemoryStorageService()
    await storage.write_json(
        "perfiles.json",
        {"profiles": [{"name": ""}, {"name": "Ana", "avatar": "no-válido"}]},
    )
    service = ProfileService(storage)

    profiles = await service.list_profiles()

    assert [profile.name for profile in profiles] == ["Ana"]
    assert profiles[0].avatar in ALLOWED_AVATARS
