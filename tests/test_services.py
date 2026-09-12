"""Tests unitarios de app/services.py.

Usan la DB efímera del fixture `db` de `conftest.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.config import AO_ALERT_THRESHOLD, DEFAULT_DEVICE_ID
from app.services import (
    fetch_by_id,
    fetch_device_breakdown,
    fetch_latest,
    fetch_readings,
    fetch_stats,
    infer_do_value,
    infer_quality_label,
    insert_readings_many,
    insert_reading,
    normalize_payload,
    rows_to_csv,
)


def test_infer_quality_label_thresholds():
    assert infer_quality_label(0) == "Muy buena"
    assert infer_quality_label(299) == "Muy buena"
    assert infer_quality_label(300) == "Aceptable"
    assert infer_quality_label(449) == "Aceptable"
    assert infer_quality_label(450) == "Mala (ventilar)"
    assert infer_quality_label(649) == "Mala (ventilar)"
    assert infer_quality_label(650) == "Muy mala / posible humo o gas"


def test_infer_do_value():
    assert infer_do_value(AO_ALERT_THRESHOLD - 1, None) is False
    assert infer_do_value(AO_ALERT_THRESHOLD, None) is True
    assert infer_do_value(0, True) is True
    assert infer_do_value(9999, False) is False


def test_normalize_unified_payload():
    data = normalize_payload({"device_id": "  dev  ", "ao": 300})
    assert data["device_id"] == "dev"
    assert data["ao"] == 300
    assert data["quality_label"] == "Aceptable"
    assert data["source"] == "api"


def test_normalize_legacy_fields():
    data = normalize_payload(
        {
            "device_id": None,
            "valor_analogico": "420",
            "voltaje": 2.5,
            "calidad_aire": 35,
        }
    )
    assert data["ao"] == 420
    assert data["voltage"] == 2.5
    assert data["device_id"] == DEFAULT_DEVICE_ID
    assert data["quality_label"] == "35"


def test_normalize_preserves_timestamp():
    dt = datetime(2025, 11, 12, 10, 30, tzinfo=timezone.utc)
    data = normalize_payload({"device_id": "d", "ao": 100, "ts": dt})
    assert data["ts"].startswith("2025-11-12T10:30:00")

    data = normalize_payload({"device_id": "d", "ao": 100, "ts": "2025-11-12T10:30:00+00:00"})
    assert data["ts"].startswith("2025-11-12T10:30:00")


def test_normalize_falls_back_on_bad_timestamp():
    data = normalize_payload({"device_id": "d", "ao": 100, "ts": "no-es-fecha"})
    assert data["ts"].startswith("20")


def test_insert_and_fetch(db):
    new_id = insert_reading({"device_id": "s1", "ao": 350, "voltage": 1.5})
    row = fetch_by_id(new_id)
    assert row["id"] == new_id
    assert row["ao"] == 350
    assert row["device_id"] == "s1"
    assert fetch_latest()["id"] == new_id


def test_insert_many_returns_count(db):
    n = insert_readings_many([{"device_id": "x", "ao": 1}] * 3)
    assert n == 3
    assert fetch_stats()["total"] == 3


def test_fetch_readings_filter_and_order(db):
    insert_readings_many(
        [
            {"device_id": "a", "ao": 100},
            {"device_id": "b", "ao": 200},
            {"device_id": "a", "ao": 300},
        ]
    )
    only_a = fetch_readings(limit=10, device_id="a")
    assert [r["device_id"] for r in only_a] == ["a", "a"]
    assert [r["ao"] for r in only_a] == [100, 300]


def test_fetch_stats_window(db):
    insert_readings_many(
        [
            {"device_id": "a", "ao": 100},
            {"device_id": "b", "ao": 200},
            {"device_id": "a", "ao": 300},
            {"device_id": "b", "ao": 400},
        ]
    )
    stats = fetch_stats(window=4)
    assert stats["total"] == 4
    assert stats["max_ao"] == 400
    assert stats["min_ao"] == 100
    assert stats["avg_ao"] == 250.0
    assert stats["latest_device_id"] == "b"


def test_stats_clamps_window(db):
    assert fetch_stats(window=10000)["window"] == 1000
    assert fetch_stats(window=0)["window"] == 1


def test_device_breakdown(db):
    insert_readings_many(
        [
            {"device_id": "a", "ao": 100},
            {"device_id": "a", "ao": 300},
            {"device_id": "b", "ao": 200},
        ]
    )
    by_id = {item["device_id"]: item for item in fetch_device_breakdown()}
    assert by_id["a"]["count"] == 2
    assert by_id["a"]["avg_ao"] == 200.0
    assert by_id["a"]["max_ao"] == 300
    assert by_id["b"]["count"] == 1


def test_rows_to_csv(db):
    insert_reading(
        {"device_id": "a", "ao": 100, "do_value": 1, "voltage": 1.5,
         "quality_label": "Bueno", "source": "manual"}
    )
    csv_text = rows_to_csv(fetch_readings(limit=5))
    lines = csv_text.strip().splitlines()
    assert lines[0].split(",") == [
        "id", "ts", "device_id", "source", "ao", "do_value", "voltage", "quality_label",
    ]
    assert len(lines) == 2
    assert "a" in lines[1] and "Bueno" in lines[1]