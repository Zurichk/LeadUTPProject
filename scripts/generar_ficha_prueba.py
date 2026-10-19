"""Genera una imagen de prueba con texto para validar el OCR.

Uso:
    python -m scripts.generar_ficha_prueba
    python -m scripts.generar_ficha_prueba --salida test/ficha.png --idioma ca

Requiere Pillow (solo para desarrollo):
    pip install Pillow
"""

from __future__ import annotations

import argparse
from pathlib import Path

TEXTS: dict[str, list[str]] = {
    "es": ["Mika", "tiene", "un", "perro", "rosa", "que", "se", "llama", "Nube"],
    "ca": [
        "La",
        "gota",
        "dels",
        "gos",
        "menuda",
        "hui",
        "al",
        "parc",
        "amb",
        "el",
        "sol",
    ],
}


def render(words: list[str], destination: Path) -> Path:
    """Dibuja las palabras en una imagen PNG grande y legible.

    Args:
        words: Palabras a escribir, una por línea.
        destination: Ruta del PNG de salida.

    Returns:
        Ruta del archivo generado.

    Raises:
        RuntimeError: Si Pillow no está instalado.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError("Necesitas Pillow: pip install Pillow") from exc

    width, height = 1000, 200 * len(words) + 100
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    font = ImageFont.load_default(size=72)
    y = 40
    for word in words:
        draw.text((60, y), word, fill="black", font=font)
        y += 200

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG")
    return destination


def main() -> None:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", default="test/ficha_prueba.png")
    parser.add_argument("--idioma", choices=sorted(TEXTS), default="es")
    args = parser.parse_args()

    path = render(TEXTS[args.idioma], Path(args.salida))
    print(f"Imagen creada: {path.resolve()}")


if __name__ == "__main__":
    main()
