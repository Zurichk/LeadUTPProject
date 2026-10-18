"""Internacionalización de la interfaz (Castellano y Valenciano).

Todas las cadenas visibles al usuario salen de :data:`TRANSLATIONS`. Las claves
desconocidas se devuelven tal cual para poder detectarlas en depuración.
"""

from __future__ import annotations

import unicodedata
from typing import Final

LanguageCode = str

SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("es", "ca")
DEFAULT_LANGUAGE: Final[str] = "es"

#: Alias aceptados para el idioma (etiquetas, cookies, ``Accept-Language``…).
_LANGUAGE_ALIASES: Final[dict[str, str]] = {
    "es": "es",
    "spa": "es",
    "castellano": "es",
    "castellà": "es",
    "es-es": "es",
    "ca": "ca",
    "cat": "ca",
    "val": "ca",
    "valenciano": "ca",
    "valencià": "ca",
    "valencian": "ca",
    "ca-es": "ca",
    "ca-valencia": "ca",
}

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "es": {
        "app.title": "LecturaFácil",
        "app.tagline": "¡Vamos a leer juntos!",
        "language.switch": "Cambiar idioma",
        "language.es": "Castellano",
        "language.ca": "Valencià",
        "profile.title": "¿Quién lee hoy?",
        "profile.add": "Añadir perfil",
        "profile.name": "Nombre",
        "profile.name_placeholder": "Escribe un nombre",
        "profile.save": "Guardar",
        "profile.cancel": "Cancelar",
        "profile.empty": "Aún no hay perfiles. Crea el primero para empezar.",
        "upload.title": "Sube la ficha de lectura",
        "upload.hint": "Haz una foto o arrastra la imagen de la ficha.",
        "upload.button": "Elegir foto",
        "upload.camera": "Hacer foto",
        "upload.processing": "Leyendo la ficha…",
        "upload.another": "Cambiar de ficha",
        "sheet.words": "Palabras de la ficha",
        "sheet.empty": "No se han encontrado palabras. Prueba con otra foto.",
        "case.label": "Cómo mostrar las letras",
        "case.upper": "MAYÚSCULAS",
        "case.lower": "minúsculas",
        "case.both": "Las dos",
        "translate.button": "Traducir al valenciano",
        "translate.button_reverse": "Traducir al castellano",
        "translate.loading": "Traduciendo…",
        "translate.done": "Traducción lista",
        "translate.unavailable": "La traducción no está disponible ahora mismo.",
        "card.listen": "Escuchar",
        "card.speak": "Decir la palabra",
        "card.listening": "Te escucho…",
        "card.heard": "Te he oído: {text}",
        "feedback.perfect": "¡Muy bien!",
        "feedback.close": "¡Casi! Inténtalo otra vez.",
        "feedback.try_again": "Vuelve a intentarlo.",
        "confetti.title": "¡Has leído las {count} palabras!",
        "error.generic": "Algo no ha funcionado. Inténtalo de nuevo.",
        "error.not_configured": "Falta configurar el servicio: {service}",
        "error.file_type": "Ese archivo no es una imagen válida.",
        "error.file_size": "La imagen es demasiado grande (máximo {max} MB).",
        "error.empty_audio": "No se ha oído nada. ¡Inténtalo otra vez!",
        "error.no_microphone_support": "Tu navegador no reconoce la voz. Usa Chrome o Edge para poder hablar.",
        "error.no_voice_available": "No hay ninguna voz en español o valenciano instalada en este dispositivo.",
        "error.empty_sheet": "La ficha no tiene palabras legibles.",
        "error.ocr_failed": "No hemos podido leer la ficha.",
        "error.storage_failed": "No hemos podido guardar la imagen.",
        "error.not_found": "No hemos encontrado lo que buscabas.",
    },
    "ca": {
        "app.title": "LecturaFácil",
        "app.tagline": "Anem a llegir junts!",
        "language.switch": "Canviar idioma",
        "language.es": "Castellà",
        "language.ca": "Valencià",
        "profile.title": "Qui llegeix hui?",
        "profile.add": "Afegir perfil",
        "profile.name": "Nom",
        "profile.name_placeholder": "Escriu un nom",
        "profile.save": "Desar",
        "profile.cancel": "Cancel·lar",
        "profile.empty": "Encara no hi ha perfils. Crea el primer per a començar.",
        "upload.title": "Puja la fitxa de lectura",
        "upload.hint": "Fes una foto o arrossega la imatge de la fitxa.",
        "upload.button": "Tria foto",
        "upload.camera": "Fer foto",
        "upload.processing": "Llegint la fitxa…",
        "upload.another": "Canviar de fitxa",
        "sheet.words": "Paraules de la fitxa",
        "sheet.empty": "No s'han trobat paraules. Prova amb una altra foto.",
        "case.label": "Com es mostren les lletres",
        "case.upper": "MAJÚSCULES",
        "case.lower": "minúscules",
        "case.both": "Les dues",
        "translate.button": "Traducir al castellà",
        "translate.button_reverse": "Traducir al valencià",
        "translate.loading": "Traduint…",
        "translate.done": "Traducció llesta",
        "translate.unavailable": "La traducció no està disponible ara mateix.",
        "card.listen": "Escoltar",
        "card.speak": "Dir la paraula",
        "card.listening": "T'escolte…",
        "card.heard": "T'he sentit: {text}",
        "feedback.perfect": "Molt bé!",
        "feedback.close": "Gairebé! Torna-ho a provar.",
        "feedback.try_again": "Torna-ho a intentar.",
        "confetti.title": "Has llegit les {count} paraules!",
        "error.generic": "Alguna cosa no ha funcionat. Torna-ho a provar.",
        "error.not_configured": "Falta configurar el servei: {service}",
        "error.file_type": "Aquest fitxer no és una imatge vàlida.",
        "error.file_size": "La imatge és massa gran (màxim {max} MB).",
        "error.empty_audio": "No s'ha sentit res. Torna-ho a provar!",
        "error.no_microphone_support": "El teu navegador no reconeix la veu. Usa Chrome o Edge per poder parlar.",
        "error.no_voice_available": "No hi ha cap veu en castellà o valencià instal·lada en aquest dispositiu.",
        "error.empty_sheet": "La fitxa no té paraules llegibles.",
        "error.ocr_failed": "No hem pogut llegir la fitxa.",
        "error.storage_failed": "No hem pogut desar la imatge.",
        "error.not_found": "No hem trobat allò que cercaves.",
    },
}


def normalize_language(value: str | None, default: str = DEFAULT_LANGUAGE) -> str:
    """Normaliza cualquier etiqueta de idioma a un código soportado.

    Args:
        value: Etiqueta recibida (``es-ES``, ``ca-ES``, ``valenciano``…).
        default: Valor devuelto si la etiqueta no es reconocida.

    Returns:
        Código de idioma soportado (``"es"`` o ``"ca"``).
    """
    if not value:
        return default
    key = value.strip().lower().replace("_", "-")
    if key in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[key]
    base = key.split("-", maxsplit=1)[0]
    return _LANGUAGE_ALIASES.get(base, default)


def strip_accents(value: str) -> str:
    """Elimina los diacríticos de una cadena.

    Args:
        value: Texto de entrada.

    Returns:
        Texto sin tildes ni diéresis.
    """
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


#: Palabras muy frecuentes: señal rápida de cada idioma.
_FREQUENT_ES: Final[frozenset[str]] = frozenset(
    {
        "los",
        "las",
        "una",
        "por",
        "para",
        "con",
        "que",
        "pero",
        "como",
        "más",
        "también",
        "está",
        "están",
        "quiero",
    }
)
_FREQUENT_CA: Final[frozenset[str]] = frozenset(
    {
        "els",
        "les",
        "amb",
        "per",
        "perquè",
        "perque",
        "més",
        "mes",
        "també",
        "tambe",
        "és",
        "està",
        "molt",
        "tota",
        "tinc",
    }
)

#: Caracteres distintivos de cada idioma con su peso.
#: ``é``, ``ó`` y ``ú`` existen en los dos idiomas, por lo que no son señales;
#: en cambio ``á`` solo aparece en castellano y ``ñ`` es muy castellanista.
_CATALAN_CHARS: Final[dict[str, int]] = {
    "à": 2,
    "è": 2,
    "ò": 2,
    "ù": 2,
    "ï": 2,
    "é": 1,
}
_SPANISH_CHARS: Final[dict[str, int]] = {"ñ": 2, "á": 2}


def detect_language(text: str) -> str:
    """Heurística simple para deducir si un texto es castellano o valenciano.

    Se comparan caracteres distintivos (``à è ò ù ï``, ``ç``, ``l·l`` y ``ñ``) y
    palabras muy frecuentes. Si el texto no aporta señales, se devuelve el
    castellano por ser el valor por defecto de la aplicación.

    Args:
        text: Texto extraído por el OCR.

    Returns:
        ``"ca"`` o ``"es"``.
    """
    lowered = text.lower()
    catalan_score = sum(
        lowered.count(ch) * weight for ch, weight in _CATALAN_CHARS.items()
    )
    catalan_score += lowered.count("ç") * 2 + lowered.count("l·l") * 3
    catalan_score += sum(lowered.count(f" {word} ") for word in _FREQUENT_CA)

    spanish_score = sum(
        lowered.count(ch) * weight for ch, weight in _SPANISH_CHARS.items()
    )
    spanish_score += sum(lowered.count(f" {word} ") for word in _FREQUENT_ES)

    return "ca" if catalan_score > spanish_score else "es"


class Translator:
    """Traductor mínimo con interpolación de variables.

    Args:
        language: Código de idioma (``"es"`` o ``"ca"``).

    Attributes:
        language: Idioma normalizado del traductor.
    """

    def __init__(self, language: str | None = None) -> None:
        self.language = normalize_language(language)

    def t(self, key: str, **kwargs: object) -> str:
        """Traduce una clave con parámetros opcionales.

        Args:
            key: Clave jerárquica (p. ej. ``"feedback.perfect"``).
            **kwargs: Valores para los marcadores ``{nombre}``.

        Returns:
            Texto traducido, o la propia clave si no existe.
        """
        catalogue = TRANSLATIONS.get(self.language, TRANSLATIONS[DEFAULT_LANGUAGE])
        template = catalogue.get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key)
        if template is None:
            return key
        return template.format(**kwargs) if kwargs else template
