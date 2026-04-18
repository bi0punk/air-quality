from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


class LegacyCSVIn(BaseModel):
    valor_analogico: int = Field(..., ge=0, le=1023)
    voltaje: Optional[float] = Field(default=None, ge=0)
    calidad_aire: Optional[str] = Field(default=None, max_length=100)


class MQ135In(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    ao: int = Field(..., ge=0, le=1023)
    do: Optional[bool] = None


class UnifiedReadingIn(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    ao: int = Field(..., ge=0, le=1023)
    do_value: Optional[bool] = None
    voltage: Optional[float] = Field(default=None, ge=0)
    quality_label: Optional[str] = Field(default=None, max_length=100)
    source: Literal['api', 'legacy_csv', 'mq135_api', 'migration', 'manual'] = 'api'
    ts: Optional[datetime] = None


class ReadingOut(BaseModel):
    id: int
    ts: datetime
    device_id: str
    ao: int
    do_value: Optional[bool] = None
    voltage: Optional[float] = None
    quality_label: Optional[str] = None
    source: str


class StatsOut(BaseModel):
    total: int
    window: int
    avg_ao: float
    min_ao: int
    max_ao: int
    latest_device_id: Optional[str] = None
    latest_ts: Optional[datetime] = None
    alert_active: bool
