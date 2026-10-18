"""Traducción de las palabras de la ficha con un modelo de Azure AI Foundry.

La traducción es **opcional y nunca bloqueante**: si el modelo no está
configurado, falla o tarda demasiado, la aplicación sigue funcionando
(la ficha ya se leyó con OCR y las tarjetas ya son jugables).

Detalles de operación reales medidos en Foundry:

* El endpoint de inferencia es ``https://<cuenta>.openai.azure.com/openai/v1``
  (no el ``services.ai.azure.com`` del proyecto, que no sirve para inferencia).
* Los despliegues *serverless* tienen arranques en frío de varios segundos, por
  lo que se usa un timeout generoso y la caché evita repetir llamadas.
* Los modelos pequeños no siempre respetan el formato pedido, así que el
  resultado se interpreta de forma tolerante (:func:`parse_translations`).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.auth import CognitiveAuth
from app.core.errors import ServiceError
from app.core.i18n import normalize_language

logger = logging.getLogger(__name__)

#: Idiomas soportados por el servicio de traducción.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("es", "ca")

_SYSTEM_PROMPT = (
    "Traduces palabras individuales de {source} a {target} para niños que "
    "aprenden a leer.\n"
    "Respondes SOLO con lineas con el formato: "
    "palabra_original -> palabra_traducida\n"
    "Reglas: una linea por palabra, mismo orden que la entrada, sin "
    "articulos, sin numeracion, sin explicaciones, sin repetir palabras.\n\n"
    "Ejemplos:\n"
    "casa -> casa\n"
    "perro -> gos\n"
    "mariposa -> papallona\n"
    "leche -> llet\n"
    "mesa -> taula\n"
)

#: Formato de mapeo ``original -> traducción``, que los modelos pequeños
#: respetan mucho mejor que pedirles JSON. Se aceptan ``->``, ``=>``, ``:`` y
#: un guion suelto, porque cada modelo elige su separador.
_ARROW_RE = re.compile(r"^\s*(?:\d+[.)-]\s*)?(.+?)\s*(?:->|=>|:|-)\s*(.+?)\s*$")

_NUMBERED_RE = re.compile(r"^\s*\d+[.)-]\s*(.+?)\s*$")
_QUOTED_RE = re.compile(r"[\"“']([^\"”']{1,40})[\"”']")


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Palabras traducidas.

    Attributes:
        pairs: Pares ``(origen, traducción)`` en el mismo orden de entrada.
        from_cache: ``True`` si todos los pares venían de la caché.
    """

    pairs: tuple[tuple[str, str], ...]
    from_cache: bool = False


class TranslationPort(Protocol):
    """Contrato del servicio de traducción."""

    async def translate(
        self,
        words: list[str],
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """Traduce una lista de palabras.

        Args:
            words: Palabras de la ficha.
            source_language: Idioma de partida.
            target_language: Idioma de destino.

        Returns:
            Palabras traducidas con su original.
        """
        ...


def _language_name(code: str) -> str:
    """Devuelve el nombre del idioma para el prompt.

    Args:
        code: Código de idioma.

    Returns:
        Nombre en el idioma de la aplicación.
    """
    return {"es": "castellano", "ca": "valenciano"}.get(code, code)


def parse_translations(content: str, expected: int) -> list[str]:
    """Extrae la lista de traducciones de la respuesta del modelo.

    Intenta, por orden: array JSON, objeto JSON con la clave ``words``, array
    JSON embebido en texto, mapeo ``original -> traducción`` (el formato que
    mejor respetan los modelos pequeños), lista numerada y palabras entre
    comillas.

    Args:
        content: Respuesta cruda del modelo.
        expected: Número de palabras que se esperaban.

    Returns:
        Lista de traducciones si se ha podido reconstruir con el tamaño
        esperado; lista vacía en caso contrario.
    """
    text = content.strip()
    if not text:
        return []

    candidates: list[str] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            candidates = [str(item) for item in parsed]
        elif isinstance(parsed, dict) and isinstance(parsed.get("words"), list):
            candidates = [str(item) for item in parsed["words"]]
    except json.JSONDecodeError:
        logger.debug("La respuesta no es JSON puro")

    if len(candidates) != expected:
        match = re.search(r"\[[^\[\]]*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                candidates = [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass

    if len(candidates) != expected:
        arrow = [
            match.groups()
            for line in text.splitlines()
            if (match := _ARROW_RE.match(line))
        ]
        if len(arrow) == expected:
            candidates = [target for _, target in arrow]

    if len(candidates) != expected:
        numbered = [
            _NUMBERED_RE.match(line).group(1)  # type: ignore[union-attr]
            for line in text.splitlines()
            if _NUMBERED_RE.match(line)
        ]
        if len(numbered) == expected:
            candidates = numbered

    if len(candidates) != expected:
        quoted = _QUOTED_RE.findall(text)
        if len(quoted) == expected:
            candidates = quoted

    return candidates if len(candidates) == expected else []


class FoundryTranslationService:
    """Traduce palabras con un modelo de chat desplegado en Foundry.

    Args:
        endpoint: Base URL de inferencia
            (``https://<cuenta>.openai.azure.com/openai/v1``).
        deployment: Nombre del deployment (por ejemplo ``Phi-4-mini-instruct``).
        auth: Proveedor de cabeceras con token de Managed Identity.
        api_key: Clave estática opcional (solo desarrollo local).
        client: Cliente HTTP asíncrono compartido.
        timeout_seconds: Tiempo máximo de espera por llamada.
        cache_size: Número máximo de traducciones guardadas en memoria.
    """

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        auth: CognitiveAuth,
        client: httpx.AsyncClient,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 25.0,
        cache_size: int = 512,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._deployment = deployment
        self._auth = auth
        self._api_key = api_key
        self._client = client
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self._cache_size = cache_size
        self._cache: dict[tuple[str, str], str] = {}

    async def _headers(self) -> dict[str, str]:
        """Devuelve las cabeceras de autenticación.

        Returns:
            Cabecera con clave estática o token de Entra ID.
        """
        if self._api_key:
            return {"api-key": self._api_key}
        return await self._auth.headers()

    async def translate(
        self,
        words: list[str],
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """Traduce las palabras que no estén ya en caché.

        Args:
            words: Palabras de la ficha.
            source_language: Idioma de partida.
            target_language: Idioma de destino.

        Returns:
            Pares (original, traducción) en el mismo orden de ``words``.

        Raises:
            ServiceError: Si el modelo no está disponible o no responde bien.
        """
        if not words:
            return TranslationResult(pairs=())
        source = normalize_language(source_language)
        target = normalize_language(target_language)
        cached = [(word, self._cache.get((word, target))) for word in words]
        pending = [word for word, value in cached if value is None]
        from_cache = not pending

        if pending:
            translated = await self._request(pending, source, target)
            for word, value in zip(pending, translated, strict=True):
                self._cache[(word, target)] = value
                while len(self._cache) > max(self._cache_size, 0):
                    self._cache.pop(next(iter(self._cache)))

        pairs = tuple(
            (word, self._cache.get((word, target), word)) for word, _ in cached
        )
        return TranslationResult(pairs=pairs, from_cache=from_cache)

    async def _request(
        self,
        words: list[str],
        source: str,
        target: str,
    ) -> list[str]:
        """Llama al modelo y reconstruye la lista de traducciones.

        Args:
            words: Palabras a traducir.
            source: Idioma de partida.
            target: Idioma de destino.

        Returns:
            Traducciones en el mismo orden que ``words``.

        Raises:
            ServiceError: Si hay error HTTP o la respuesta no es utilizable.
        """
        payload = {
            "model": self._deployment,
            "messages": [
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT.format(
                        source=_language_name(source), target=_language_name(target)
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Traduce de {_language_name(source)} a "
                        f"{_language_name(target)} estas palabras, una por "
                        f"línea:\n" + "\n".join(words)
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 400,
        }
        headers = {
            **await self._headers(),
            "Content-Type": "application/json",
        }
        try:
            response = await self._client.post(
                f"{self._endpoint}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            logger.warning("El modelo de traducción ha agotado el tiempo")
            raise ServiceError(
                "error.generic", status_code=504, code="translation_timeout"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Fallo de red al traducir: %s", exc)
            raise ServiceError(
                "error.generic", status_code=502, code="translation_network_error"
            ) from exc

        if response.status_code >= 400:
            logger.error("El modelo de traducción respondió %s", response.status_code)
            raise ServiceError(
                "error.generic", status_code=502, code="translation_error"
            )

        content = _extract_message(response.json())
        translations = parse_translations(content, len(words))
        if not translations:
            logger.warning("Respuesta de traducción no utilizable: %.120s", content)
            raise ServiceError(
                "error.generic", status_code=502, code="translation_unparsable"
            )
        return translations


class UnavailableTranslationService:
    """Servicio de traducción desactivado.

    Permite que la aplicación arranque sin Foundry configurado.
    """

    async def translate(
        self,
        words: list[str],
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """Informa de que la traducción no está disponible.

        Args:
            words: Palabras solicitadas.
            source_language: Idioma de partida.
            target_language: Idioma de destino.

        Raises:
            ServiceError: Siempre, con código ``translation_not_configured``.
        """
        raise ServiceError(
            "error.generic",
            status_code=503,
            code="translation_not_configured",
        )


def _extract_message(payload: dict[str, object]) -> str:
    """Extrae el contenido del primer mensaje de la respuesta.

    Args:
        payload: Cuerpo JSON devuelto por el modelo.

    Returns:
        Texto generado por el modelo (vacío si no se puede leer).
    """
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    return str(message.get("content", "") or "")
