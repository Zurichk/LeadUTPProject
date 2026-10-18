"""Contrato de la infraestructura de OCR.

Se abstrae porque la aplicación admite dos proveedores de Azure
(``Azure AI Vision`` y ``Azure AI Document Intelligence``) y necesita dobles en
las pruebas.
"""

from __future__ import annotations

from typing import Protocol

from app.services.ocr.models import OcrResult


class OcrPort(Protocol):
    """Puerto de lectura de texto desde una imagen.

    Los adaptadores reciben los bytes ya validados por la capa de
    presentación y devuelven el texto extraído.
    """

    async def read_image(self, image: bytes, *, filename: str) -> OcrResult:
        """Extrae el texto de una imagen.

        Args:
            image: Bytes de la imagen de la ficha.
            filename: Nombre original (solo para diagnóstico).

        Returns:
            Texto y palabras detectados por el motor.

        Raises:
            ServiceError: Si el proveedor falla o responde con un error.
        """
        ...
