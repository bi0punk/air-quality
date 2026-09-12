"""Tests de app/legacy_import.py (CSV y SQLite, idempotencia)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from app.legacy_import import import_legacy_csv, import_known_legacy_files, import_legacy_sqlite
from app.services import fetch_readings, fetch_stats


def _write_csv(path: Path) -> None:
    pd.DataFrame(
        {
            "valor_analogico": [200, 300],
            "voltaje": [1.0, 2.0],
            "calidad_aire": ["Buena", "Regular"],
        }
    ).to_csv(path, index=False)


def _write_sqlite(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE readings (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, device_id TEXT, ao INTEGER, do REAL)"
    )
    con.executemany(
        "INSERT INTO readings (ts, device_id, ao, do) VALUES (?, ?, ?, ?)",
        [
            ("2025-11-12T10:00:00+00:00", "dev1", 100, 0),
            ("2025-11-12T10:01:00+00:00", "dev2", 700, 1),
        ],
    )
    con.commit()
    con.close()


def test_import_csv_is_idempotent(db, tmp_path: Path):
    csv_path = tmp_path / "datos.csv"
    _write_csv(csv_path)

    assert import_legacy_csv(csv_path) == 2
    assert import_legacy_csv(csv_path) == 0

    assert fetch_stats()["total"] == 2
    rows = fetch_readings(limit=10)
    assert rows[0]["ao"] == 200
    assert rows[0]["quality_label"] == "Buena"
    assert rows[0]["source"] == "legacy_csv"


def test_import_sqlite_is_idempotent(db, tmp_path: Path):
    db_path = tmp_path / "mq135.db"
    _write_sqlite(db_path)

    assert import_legacy_sqlite(db_path) == 2
    assert import_legacy_sqlite(db_path) == 0

    rows = fetch_readings(limit=10)
    assert len(rows) == 2
    assert rows[0]["ts"].startswith("2025-11-12T10:00:00")
    assert rows[0]["device_id"] == "dev1"
    assert rows[1]["do_value"] == 1
    assert rows[1]["source"] == "migration"


def test_import_known_files_skips_missing(db, tmp_path: Path):
    results = import_known_legacy_files(tmp_path)
    assert results == {"legacy_csv": 0, "legacy_sqlite": 0}