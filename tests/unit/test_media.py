"""Pruebas de la detección del tipo de imagen."""

from __future__ import annotations

import pytest

from app.core.media import resolve_image_content_type, sniff_image_content_type

ALLOWED = ("image/jpeg", "image/png", "image/webp", "image/bmp")
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"0" * 16


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (WEBP, "image/webp"),
        (b"BM" + b"0" * 32, "image/bmp"),
        (b"texto plano", None),
        (b"", None),
    ],
)
def test_sniff_image_content_type(content: bytes, expected: str | None) -> None:
    """Se reconoce el formato real del archivo."""
    assert sniff_image_content_type(content) == expected


def test_resolve_returns_the_real_type() -> None:
    """El tipo real del archivo es el que se guarda."""
    assert resolve_image_content_type(PNG, ALLOWED) == "image/png"
    assert resolve_image_content_type(JPEG, ALLOWED) == "image/jpeg"


def test_text_file_is_rejected_even_with_image_extension() -> None:
    """Un archivo de texto renombrado a .jpg se rechaza."""
    assert resolve_image_content_type(b"no soy una imagen", ALLOWED) is None


def test_disallowed_format_is_rejected() -> None:
    """Un formato no admitido por la configuración se rechaza."""
    assert resolve_image_content_type(b"GIF89a" + b"0" * 20, ALLOWED) is None
