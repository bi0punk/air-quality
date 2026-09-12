"""Tests de endpoints (smoke) para Air Quality Fusion API.

Usan la DB efímera provista por el fixture `client` de `conftest.py`.
"""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_info(client):
    r = client.get("/api/info")
    assert r.status_code == 200
    assert "Air Quality Fusion API" in r.text


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

    # El label legacy se preserva y valor_analogico se mapea a ao
    latest = client.get("/api/readings/latest").json()
    assert latest["ao"] == 420
    assert latest["quality_label"] == "Regular"

    # Endpoint legado /api/mq135
    r = client.post("/api/mq135", json={"device_id": "dev1", "ao": 500, "do": 0})
    assert r.status_code == 201, r.text
    assert r.json()["device_id"] == "dev1"


def test_csv_export(client):
    client.post("/api/readings", json={"device_id": "d", "ao": 100, "source": "manual"})
    r = client.get("/api/export/csv", params={"limit": 100})
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    header = r.text.splitlines()[0]
    assert "device_id" in header and "quality_label" in header


def test_latest_includes_full_row(client):
    client.post("/api/readings", json={"device_id": "d1", "ao": 250, "do_value": 0, "voltage": 1.2})
    latest = client.get("/api/readings/latest").json()
    assert "device_id" in latest and latest["device_id"] == "d1"
    assert "do_value" in latest and latest["do_value"] == 0


def test_stats_endpoint(client):
    client.post("/api/readings", json={"device_id": "a", "ao": 100, "source": "manual"})
    client.post("/api/readings", json={"device_id": "b", "ao": 400, "source": "manual"})
    r = client.get("/api/stats", params={"window": 5})
    assert r.status_code == 200
    stats = r.json()
    assert stats["total"] == 2
    assert stats["max_ao"] == 400
    assert stats["min_ao"] == 100
    assert stats["avg_ao"] == 250.0
    assert stats["alert_active"] is False


def test_devices_endpoint(client):
    client.post("/api/readings", json={"device_id": "dev-a", "ao": 100, "source": "manual"})
    client.post("/api/readings", json={"device_id": "dev-a", "ao": 300, "source": "manual"})
    client.post("/api/readings", json={"device_id": "dev-b", "ao": 200, "source": "manual"})
    r = client.get("/api/devices")
    assert r.status_code == 200
    by_id = {item["device_id"]: item for item in r.json()}
    assert by_id["dev-a"]["count"] == 2
    assert by_id["dev-b"]["count"] == 1
    assert by_id["dev-a"]["max_ao"] == 300


def test_list_readings_device_filter(client):
    client.post("/api/readings", json={"device_id": "alpha", "ao": 100, "source": "manual"})
    client.post("/api/readings", json={"device_id": "beta", "ao": 200, "source": "manual"})
    r = client.get("/api/readings", params={"device_id": "alpha"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["device_id"] == "alpha"
    assert items[0]["source"] == "manual"


def test_dashboard_renders(client):
    for path in ("/", "/dashboard"):
        r = client.get(path)
        assert r.status_code == 200
        assert "Air Quality Fusion Dashboard" in r.text


def test_invalid_ao_rejected(client):
    r = client.post("/api/readings", json={"device_id": "d", "ao": 99999})
    assert r.status_code == 422


def test_latest_404_when_empty(client):
    assert client.get("/api/readings/latest").status_code == 404