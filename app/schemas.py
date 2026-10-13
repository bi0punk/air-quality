from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def validate_reading_payload(payload: BaseModel) -> None:
    """Valida rangos numéricos de los campos soportados."""
    for field_name in ["valor_analogico", "voltaje", "ao"]:
        val = getattr(payload, field_name, None)
        if val is None:
            continue
        try:
            v = float(val)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} debe ser numérico") from None
        if field_name == "valor_analogico" and not (0 <= v <= 1023):
            raise ValueError("valor_analogico debe estar entre 0 y 1023")
        if field_name == "voltaje" and not (0 <= v <= 5.0):
            raise ValueError("voltaje debe estar entre 0 y 5.0")
        if field_name == "ao" and not (0 <= v <= 4096):
            raise ValueError("ao debe estar entre 0 y 4096")


def reading_to_dict(reading: BaseModel) -> dict[str, Any]:
    """Convierte un modelo Pydantic a diccionario usando los alias de campo."""
    data = reading.model_dump(by_alias=True)
    if "do_value" not in data and "do" in data:
        data["do_value"] = data.pop("do")
    return data


class ReadingSource(StrEnum):
    LEGACY = "legacy"
    LEGACY_CSV = "legacy_csv"
    MQ135 = "mq135"
    MQ135_API = "mq135_api"
    API = "api"
    MANUAL = "manual"
    MIGRATION = "migration"


# Lectura unificada (acepta múltiples fuentes)
class UnifiedReadingIn(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    source: ReadingSource = ReadingSource.API
    ao: float | None = Field(None, ge=0, le=4096, alias="ao")
    do_value: float | None = Field(None, ge=0, le=1, alias="do")
    voltage: float | None = Field(None, ge=0, le=5.0, alias="voltage")
    quality_label: str | None = Field(None, alias="calidad_aire")

    model_config = {"populate_by_name": True, "extra": "allow"}


# Resumen de una lectura
class ReadingOut(BaseModel):
    id: int
    ts: str
    device_id: str
    ao: float | None = None
    do_value: int | None = None
    voltage: float | None = None
    quality_label: str | None = None


# Payload legacy Flask /data
class LegacyCSVIn(BaseModel):
    device_id: str | None = Field(None, max_length=64)
    valor_analogico: float | None = Field(None, ge=0, le=1023)
    voltaje: float | None = Field(None, ge=0, le=5.0)
    calidad_aire: str | float | None = None
    source: ReadingSource = ReadingSource.LEGACY

    @field_validator("calidad_aire", mode="before")
    @classmethod
    def flexibility_calidad_aire(cls, v: Any) -> Any:
        if v is None or isinstance(v, str):
            return v
        try:
            return float(v)
        except (ValueError, TypeError):
            return v


# Payload MQ135 actual
class MQ135In(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    ao: float = Field(..., ge=0, le=4096)
    do: float = Field(..., ge=0, le=1)
    quality_label: str | None = None


# Item de listado
class ReadingListItem(BaseModel):
    id: int
    ts: str
    device_id: str
    ao: float | None = None
    do_value: float | None = None
    voltage: float | None = None
    quality_label: str | None = None
    source: ReadingSource

    model_config = {"from_attributes": True}
