"""Configuración del logging de la aplicación."""

from __future__ import annotations

import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configura el logging global en la salida estándar.

    Args:
        level: Nivel mínimo de log (``DEBUG``, ``INFO``, ``WARNING``…).
    """
    logging.basicConfig(
        level=level.upper(),
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
        logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
