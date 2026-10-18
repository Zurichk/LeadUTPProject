"""DTOs de los perfiles de lectura."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ProfileOut(BaseModel):
    """Perfil devuelto al cliente.

    Attributes:
        id: Identificador del perfil.
        name: Nombre del niño o niña.
        avatar: Emoji del avatar.
        language: Idioma preferido.
    """

    id: str
    name: str = Field(min_length=1, max_length=24)
    avatar: str
    language: str = Field(default="es", pattern="^(es|ca)$")


class ProfileCreate(BaseModel):
    """Petición de alta de perfil.

    Attributes:
        name: Nombre del perfil.
        avatar: Emoji del avatar (debe estar en la lista permitida).
        language: Idioma preferido.
    """

    name: str = Field(min_length=1, max_length=24)
    avatar: str = Field(min_length=1, max_length=8)
    language: str = Field(default="es", pattern="^(es|ca)$")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        """Colapsa los espacios del nombre.

        Args:
            value: Nombre recibido.

        Returns:
            Nombre sin espacios duplicados.

        Raises:
            ValueError: Si el nombre queda vacío tras limpiar.
        """
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("El nombre no puede estar vacío")
        return cleaned
