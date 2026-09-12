"""Tests unitarios de app/schemas.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    LegacyCSVIn,
    MQ135In,
    ReadingSource,
    UnifiedReadingIn,
    reading_to_dict,
    validate_reading_payload,
)


def test_reading_source_members():
    assert ReadingSource.LEGACY.value == "legacy"
    assert ReadingSource.LEGACY_CSV.value == "legacy_csv"
    assert ReadingSource.MQ135_API.value == "mq135_api"
    assert ReadingSource.MIGRATION.value == "migration"
    assert ReadingSource.MANUAL.value == "manual"


def test_unified_accepts_valid_payload():
    reading = UnifiedReadingIn(device_id="d", ao=500, do_value=1, voltage=1.5)
    validate_reading_payload(reading)
    assert reading.device_id == "d"


def test_unified_rejects_ao_out_of_range():
    with pytest.raises(ValidationError):
        UnifiedReadingIn(device_id="d", ao=5000)
    with pytest.raises(ValidationError):
        UnifiedReadingIn(device_id="d", voltage=9.0)


def test_legacy_accepts_aliased_fields():
    legacy = LegacyCSVIn(valor_analogico=420, voltaje=2.5, calidad_aire="Regular")
    assert legacy.valor_analogico == 420
    assert legacy.voltaje == 2.5
    assert legacy.calidad_aire == "Regular"
    assert legacy.source is ReadingSource.LEGACY


def test_mq135_payload():
    mq = MQ135In(device_id="dev1", ao=500, do=0)
    assert mq.device_id == "dev1"
    assert mq.do == 0


def test_reading_to_dict_preserves_aliases():
    reading = UnifiedReadingIn(device_id="d", ao=100, do_value=1, quality_label="Bueno")
    data = reading_to_dict(reading)
    assert data["device_id"] == "d"
    assert data["do_value"] == 1
    assert data["calidad_aire"] == "Bueno"


def test_reading_to_dict_remaps_do():
    legacy = LegacyCSVIn(valor_analogico=420)
    data = reading_to_dict(legacy)
    assert "valor_analogico" in data
    assert data["source"] == "legacy"