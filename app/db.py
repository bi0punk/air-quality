from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            '''
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                device_id TEXT NOT NULL,
                ao INTEGER NOT NULL,
                do_value INTEGER,
                voltage REAL,
                quality_label TEXT,
                source TEXT NOT NULL DEFAULT 'api'
            );

            CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_readings_device ON readings(device_id);

            CREATE TABLE IF NOT EXISTS import_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(source_type, source_path)
            );
            '''
        )
