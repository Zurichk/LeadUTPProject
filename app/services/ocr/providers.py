"""Adaptadores de OCR sobre Azure AI Vision y Azure AI Document
Intelligence.

Ambos hablan REST y se autentican con la Managed Identity
(``DefaultAzureCredential``) o, en desarrollo local, con una clave estática.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.auth import CognitiveAuth
from app.core.errors import ServiceError
from app.services.ocr.models import OcrResult, OcrWord

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 1.5


def _normalize_polygon(polygon: object) -> tuple[tuple[float, float], ...]:
    """Normaliza el polígono de una palabra a pares de coordenadas.

    Acepta los dos formatos que usan los servicios:

    * Azure AI Vision: lista de objetos ``{"x": .., "y": ..}``.
    * Document Intelligence: lista plana de números ``[x1, y1, x2, y2, ...]``.

    Args:
        polygon: Polígono tal y como llega en la respuesta.

    Returns:
        Tupla de pares ``(x, y)``; vacía si el formato no se reconoce.
    """
    if not isinstance(polygon, list):
        return ()
    if polygon and isinstance(polygon[0], dict):
        points: list[tuple[float, float]] = []
        for point in polygon:
            if isinstance(point, dict) and "x" in point and "y" in point:
                points.append((float(point["x"]), float(point["y"])))
        return tuple(points)
    numbers = [float(value) for value in polygon if isinstance(value, int | float)]
    return tuple(zip(numbers[::2], numbers[1::2], strict=False))


def _blocks_from(read_result: dict[str, Any]) -> list[Any]:
    """Obtiene los bloques de texto de un ``readResult``.

    Azure AI Vision devuelve ``readResult.blocks`` directamente, mientras que
    otras versiones del mismo servicio lo envuelven en
    ``analyzeResult.readResult.pages[].blocks``. Se admiten ambos.

    Args:
        read_result: Objeto ``readResult`` de la respuesta.

    Returns:
        Lista de bloques de texto (puede estar vacía).
    """
    blocks = read_result.get("blocks")
    if isinstance(blocks, list):
        return blocks
    collected: list[Any] = []
    pages = read_result.get("pages")
    if isinstance(pages, list):
        for page in pages:
            if isinstance(page, dict) and isinstance(page.get("blocks"), list):
                collected.extend(page["blocks"])
    return collected


def _vision_read_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Localiza el objeto ``readResult`` en la respuesta de Azure AI Vision.

    Args:
        payload: Cuerpo JSON devuelto por el servicio.

    Returns:
        Objeto ``readResult`` (vacío si no se encuentra).
    """
    if not isinstance(payload, dict):
        return {}
    direct = payload.get("readResult")
    if isinstance(direct, dict):
        return direct
    nested = payload.get("analyzeResult")
    if isinstance(nested, dict):
        inner = nested.get("readResult")
        if isinstance(inner, dict):
            return inner
    return {}


def _parse_vision_words(payload: dict[str, Any]) -> list[OcrWord]:
    """Extrae las palabras de la respuesta de Azure AI Vision (Read 4.0).

    Args:
        payload: Cuerpo JSON devuelto por el servicio.

    Returns:
        Lista de palabras con su confianza y posición.
    """
    words: list[OcrWord] = []
    for block in _blocks_from(_vision_read_result(payload)):
        if not isinstance(block, dict):
            continue
        for line in block.get("lines", []) or []:
            if not isinstance(line, dict):
                continue
            for word in line.get("words", []) or []:
                if not isinstance(word, dict):
                    continue
                text = str(word.get("text", "")).strip()
                if text:
                    words.append(
                        OcrWord(
                            text=text,
                            confidence=float(word.get("confidence", 0.0)),
                            bbox=_normalize_polygon(word.get("boundingPolygon")),
                        )
                    )
    return words


def _parse_document_intelligence_words(payload: dict[str, Any]) -> list[OcrWord]:
    """Extrae las palabras de la respuesta de Document Intelligence.

    Args:
        payload: Cuerpo JSON con ``analyzeResult``.

    Returns:
        Lista de palabras con su confianza y posición.
    """
    words: list[OcrWord] = []
    analyze_result = (
        payload.get("analyzeResult", {}) if isinstance(payload, dict) else {}
    )
    for page in analyze_result.get("pages", []) or []:
        for line in page.get("lines", []) or []:
            for word in line.get("words", []) or []:
                text = str(word.get("content", "")).strip()
                if text:
                    words.append(
                        OcrWord(
                            text=text,
                            confidence=float(word.get("confidence", 0.0)),
                            bbox=_normalize_polygon(word.get("polygon")),
                        )
                    )
    return words


def _join_words(words: list[OcrWord]) -> str:
    """Construye el texto plano de la página a partir de las palabras.

    Args:
        words: Palabras en orden de lectura.

    Returns:
        Texto separado por espacios.
    """
    return " ".join(word.text for word in words)


class AzureVisionReadOcr:
    """OCR con Azure AI Vision (API Read 4.0).

    Args:
        endpoint: Endpoint del recurso (p. ej. ``https://r.cognitiveservices.azure.com``).
        auth: Proveedor de cabeceras de autenticación.
        client: Cliente HTTP asíncrono.
        api_version: Versión de la API de análisis de imagen.
    """

    def __init__(
        self,
        endpoint: str,
        auth: CognitiveAuth,
        client: httpx.AsyncClient,
        api_version: str = "2024-02-01",
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._auth = auth
        self._client = client
        self._api_version = api_version

    async def read_image(self, image: bytes, *, filename: str) -> OcrResult:
        """Analiza una imagen con el servicio de visión.

        Args:
            image: Bytes de la imagen.
            filename: Nombre original, solo para logs.

        Returns:
            Texto y palabras detectados.

        Raises:
            ServiceError: Si el servicio devuelve un error o un cuerpo vacío.
        """
        url = (
            f"{self._endpoint}/computervision/imageanalysis:analyze"
            f"?api-version={self._api_version}&features=read"
        )
        headers = {
            **await self._auth.headers(),
            "Content-Type": "application/octet-stream",
        }
        logger.info("Analizando imagen con Azure AI Vision: %s", filename)
        response = await self._client.post(url, content=image, headers=headers)
        if response.status_code >= 400:
            logger.error(
                "Azure AI Vision respondió %s: %s",
                response.status_code,
                response.text[:200],
            )
            raise ServiceError("error.ocr_failed", status_code=502, code="vision_error")
        words = _parse_vision_words(response.json())
        if not words:
            raise ServiceError("error.empty_sheet", status_code=422, code="empty_sheet")
        return OcrResult(text=_join_words(words), words=tuple(words), provider="vision")


class AzureDocumentIntelligenceOcr:
    """OCR con Azure AI Document Intelligence (``prebuilt-read``).

    Args:
        endpoint: Endpoint del recurso.
        auth: Proveedor de cabeceras de autenticación.
        client: Cliente HTTP asíncrono.
        api_version: Versión de la API REST.
        max_wait_seconds: Tiempo máximo de espera del análisis asíncrono.
    """

    def __init__(
        self,
        endpoint: str,
        auth: CognitiveAuth,
        client: httpx.AsyncClient,
        api_version: str = "2024-11-30",
        max_wait_seconds: float = 60.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._auth = auth
        self._client = client
        self._api_version = api_version
        self._max_wait_seconds = max_wait_seconds

    async def read_image(self, image: bytes, *, filename: str) -> OcrResult:
        """Envía la imagen a Document Intelligence y espera al resultado.

        Args:
            image: Bytes de la imagen.
            filename: Nombre original, solo para logs.

        Returns:
            Texto y palabras detectados.

        Raises:
            ServiceError: Si el análisis falla o no devuelve palabras.
        """
        url = (
            f"{self._endpoint}/documentintelligence/documentModels/"
            f"prebuilt-read:analyze?api-version={self._api_version}"
        )
        headers = {
            **await self._auth.headers(),
            "Content-Type": "application/octet-stream",
        }
        logger.info("Analizando imagen con Document Intelligence: %s", filename)
        response = await self._client.post(url, content=image, headers=headers)
        if response.status_code >= 400:
            logger.error(
                "Document Intelligence respondió %s: %s",
                response.status_code,
                response.text[:200],
            )
            raise ServiceError(
                "error.ocr_failed", status_code=502, code="document_intelligence_error"
            )
        operation_url = response.headers.get("operation-location")
        if not operation_url:
            payload = response.json()
            words = _parse_document_intelligence_words(payload)
        else:
            words = await self._await_result(operation_url)
        if not words:
            raise ServiceError("error.empty_sheet", status_code=422, code="empty_sheet")
        return OcrResult(
            text=_join_words(words),
            words=tuple(words),
            provider="document_intelligence",
        )

    async def _await_result(self, operation_url: str) -> list[OcrWord]:
        """Consulta el estado del análisis hasta que finaliza.

        Args:
            operation_url: URL de operación devuelta por el servicio.

        Returns:
            Palabras detectadas en la página.

        Raises:
            ServiceError: Si el análisis termina en error o se agota el tiempo.
        """
        headers = await self._auth.headers()
        deadline = asyncio.get_running_loop().time() + self._max_wait_seconds
        while True:
            response = await self._client.get(operation_url, headers=headers)
            if response.status_code >= 400:
                raise ServiceError(
                    "error.ocr_failed",
                    status_code=502,
                    code="document_intelligence_error",
                )
            payload = response.json()
            status = str(payload.get("status", "")).lower()
            if status == "succeeded":
                return _parse_document_intelligence_words(payload)
            if status == "failed":
                logger.error("Document Intelligence falló: %s", payload.get("error"))
                raise ServiceError(
                    "error.ocr_failed",
                    status_code=502,
                    code="document_intelligence_error",
                )
            if asyncio.get_running_loop().time() > deadline:
                raise ServiceError(
                    "error.ocr_failed", status_code=504, code="ocr_timeout"
                )
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


class DemoOcr:
    """OCR de demostración para usar la interfaz sin credenciales de Azure.

    Args:
        text: Texto fijo que se devuelve como si fuese el de la ficha.
    """

    DEFAULT_TEXT = (
        "Mika té un gos petit. El gos és rosa i es diu Nube. Mentre juga al parc."
    )

    def __init__(self, text: str | None = None) -> None:
        self._text = text or self.DEFAULT_TEXT

    async def read_image(self, image: bytes, *, filename: str) -> OcrResult:
        """Devuelve un texto fijo, ignorando la imagen.

        Args:
            image: Bytes de la imagen (no se usan).
            filename: Nombre original (no se usa).

        Returns:
            Resultado con el texto de demostración troceado en palabras.
        """
        words = tuple(
            OcrWord(text=token, confidence=0.99)
            for token in self._text.split()
            if token.strip(".")
        )
        return OcrResult(
            text=" ".join(w.text for w in words), words=words, provider="demo"
        )
