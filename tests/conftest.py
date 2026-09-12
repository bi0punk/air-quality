"""Fixtures compartidos: DB efímera y cliente HTTP de pruebas."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Apunta la configuración a una DB efímera y recarga los módulos.

    Los módulos leen las variables de entorno al importarse, así que se
    recargan tras fijar AIR_QUALITY_DB_PATH para aislar cada test.
    """
    db = tmp_path / "test_air_quality.db"
    monkeypatch.setenv("AIR_QUALITY_DB_PATH", str(db))
    monkeypatch.setenv("AIR_QUALITY_IMPORT_ON_STARTUP", "0")
    for name in ("app.config", "app.db", "app.services", "app.legacy_import", "app.main"):
        importlib.reload(importlib.import_module(name))
    return db


@pytest.fixture
def db(tmp_db: Path) -> Path:
    """DB efímera inicializada (esquema creado)."""
    from app.db import init_db
    init_db()
    return tmp_db


@pytest.fixture
def client(tmp_db: Path):
    from app.main import app

    with TestClient(app) as c:
        yield c