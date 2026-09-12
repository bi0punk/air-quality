from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


def validate_reading_payload(payload: BaseModel) -> None:
    """Validación centralizada de payloads de lectura."""
    # Para cualquier source, validar campos numéricos si vienen
    for field_name in ['valor_analogico', 'voltaje', 'ao']:
        val = getattr(payload, field_name, None)
        if val is not None:
            try:
                v = float(val)
                if field_name == 'valor_analogico' and not (0 <= v <= 1023):
                    raise ValueError('valor_analogico debe estar entre 0 y 1023')
                if field_name == 'voltaje' and not (0 <= v <= 5.0):
                    raise ValueError('voltaje debe estar entre 0 y 5.0')
                if field_name == 'ao' and not (0 <= v <= 4096):
                    raise ValueError('ao debe estar entre 0 y 4096')
            except (ValueError, TypeError):
                raise ValueError(f'{field_name} debe ser numérico')


def reading_to_dict(reading: BaseModel) -> dict[str, Any]:
    """Convierte un modelo Pydantic a diccionario, usando alias."""
    data = reading.model_dump(by_alias=True)
    # Asegurar que do_value venga de do si es necesario
    if "do_value" not in data and "do" in data:
        data["do_value"] = data.pop("do")
    # Convertir calidad_aire a None si es string (para compatibilidad)
    if "calidad_aire" in data and isinstance(data["calidad_aire"], str):
        data["calidad_aire"] = None
    return data


class QualityLabel(str, Enum):
    EXCELENTE = "excelente"
    BUENO = "bueno"
    MODERADO = "moderado"
    MALO = "malo"
    MUCHO_MALO = "mucho malo"


class ReadingSource(str, Enum):
    LEGACY = "legacy"
    MQ135 = "mq135"
    API = "api"
    MANUAL = "manual"


# Schema para lectura unificada (acepta multiple fuentes)
class UnifiedReadingIn(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    source: ReadingSource = ReadingSource.API
    ao: Optional[float] = Field(None, ge=0, le=4096, alias="ao")
    do_value: Optional[float] = Field(None, ge=0, le=1, alias="do")
    voltage: Optional[float] = Field(None, ge=0, le=5.0, alias="voltage")
    quality_label: Optional[str] = Field(None, alias="calidad_aire")
    
    model_config = {"populate_by_name": True, "extra": "allow"}


# Schema para respuesta
class ReadingOut(BaseModel):
    id: int
    ts: str
    quality_label: Optional[str] = None
    raw_ao: Optional[float] = None
    raw_voltaje: Optional[float] = None


# Schema legacy CSV - campos sueltos, se leen lo que vienen JSON
class LegacyCSVIn(BaseModel):
    device_id: Optional[str] = Field(None, max_length=64, alias="device_id")
    valor_analogico: Optional[float] = Field(None, ge=0, le=1023, alias="valor_analogico")
    voltaje: Optional[float] = Field(None, ge=0, le=5.0, alias="voltaje")
    calidad_aire: Optional[str] = Field(None, alias="calidad_aire")
    source: ReadingSource = ReadingSource.LEGACY
    
    @validator('calidad_aire', pre=True)
    def flexibility_calidad_aire(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return v
        try:
            return float(v)
        except (ValueError, TypeError):
            return v


# Schema MQ135
class MQ135In(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    ao: float = Field(..., ge=0, le=4096)
    do: float = Field(..., ge=0, le=1)
    quality_label: Optional[str] = None


# Schema para salida de lista
class ReadingListItem(BaseModel):
    id: int
    ts: str
    device_id: str
    ao: Optional[float] = None
    do_value: Optional[float] = None
    voltage: Optional[float] = None
    quality_label: Optional[str] = None
    source: ReadingSource
    
    model_config = {"from_attributes": True}
