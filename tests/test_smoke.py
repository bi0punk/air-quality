"""Smoke tests para Air Quality Fusion API.

Usan TestClient de FastAPI y una DB efímera vía AIR_QUALITY_DB_PATH para no tocar
el data/air_quality.db real.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "test_air_quality.db"
    monkeypatch.setenv("AIR_QUALITY_DB_PATH", str(db))
    monkeypatch.setenv("AIR_QUALITY_IMPORT_ON_STARTUP", "0")
    # Reimport config para que tome el nuevo path antes de arrancar la app.
    import importlib

    import app.config as config
    importlib.reload(config)
    import app.db as dbmod
    importlib.reload(dbmod)
    import app.services as services
    importlib.reload(services)
    import app.main as mainmod
    importlib.reload(mainmod)
    yield mainmod.app


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_read_unified(client):
    payload = {
        "device_id": "sensor-test",
        "ao": 350,
        "do_value": 1,
        "voltage": 1.7,
        "quality_label": "Bueno",
        "source": "manual",
    }
    r = client.post("/api/readings", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["device_id"] == "sensor-test"
    assert created["ao"] == 350

    latest = client.get("/api/readings/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == created["id"]

    listed = client.get("/api/readings", params={"limit": 10})
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())


def test_legacy_endpoints_compat(client):
    # Endpoint legado Flask /data
    r = client.post("/data", json={"valor_analogico": 420, "voltaje": 2.1, "calidad_aire": "Regular"})
    assert r.status_code == 200
    assert r.json()["compat_mode"] == "legacy_flask"

    # Endpoint legado /api/mq135
    r = client.post("/api/mq135", json={"device_id": "dev1", "ao": 500, "do": 0})
    assert r.status_code == 200
    assert r.json()["device_id"] == "dev1"


def test_csv_export(client):
    client.post("/api/readings", json={"device_id": "d", "ao": 100, "source": "manual"})
    r = client.get("/api/export/csv", params={"limit": 100})
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "device_id" in r.text


@pytest.fixture
def client(tmp_db):
    from fastapi.testclient import TestClient

    with TestClient(tmp_db) as c:
        yield c
