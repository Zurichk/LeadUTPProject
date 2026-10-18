"""Detección del tipo real de una imagen a partir de sus bytes.

El navegador puede enviar un ``Content-Type`` poco fiable (``application/octet-stream``
es habitual al arrastrar archivos o en fotos de iPhone). En lugar de confiar en
la cabecera, se comprueba la firma binaria del archivo y se guarda el tipo
real en Blob Storage.
"""

from __future__ import annotations

#: Firmas binarias de los formatos de imagen admitidos.
_IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"BM", "image/bmp"),
)


def sniff_image_content_type(content: bytes) -> str | None:
    """Devuelve el tipo MIME real de una imagen.

    Args:
        content: Bytes iniciales del archivo.

    Returns:
        Tipo MIME detectado o ``None`` si el formato no está admitido.
    """
    if not content:
        return None
    for signature, mime_type in _IMAGE_SIGNATURES:
        if content.startswith(signature):
            return mime_type
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def resolve_image_content_type(
    content: bytes,
    allowed_types: tuple[str, ...],
) -> str | None:
    """Resuelve el tipo de una imagen subida validando su contenido.

    El tipo declarado por el cliente no se usa para decidir: un archivo de
    texto renombrado a ``.jpg`` debe rechazarse igual que un PDF.

    Args:
        content: Bytes del archivo.
        allowed_types: Tipos MIME aceptados por la aplicación.

    Returns:
        El tipo MIME real si la imagen es válida; ``None`` si se rechaza.
    """
    detected = sniff_image_content_type(content)
    if detected is not None and detected in allowed_types:
        return detected
    return None
