from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Optional

import pandas as pd

from .config import DEFAULT_DEVICE_ID
from .db import connection
from .schemas import UnifiedReadingIn
from .services import insert_reading, infer_quality_label


def _already_imported(source_type: str, source_path: Path) -> bool:
    with connection() as conn:
        row = conn.execute(
            'SELECT 1 FROM import_registry WHERE source_type = ? AND source_path = ? LIMIT 1',
            (source_type, str(source_path.resolve())),
        ).fetchone()
        return row is not None


def _mark_imported(source_type: str, source_path: Path, row_count: int) -> None:
    with connection() as conn:
        conn.execute(
            '''
            INSERT OR IGNORE INTO import_registry (source_type, source_path, imported_at, row_count)
            VALUES (?, ?, ?, ?)
            ''',
            (source_type, str(source_path.resolve()), datetime.now(timezone.utc).isoformat(), int(row_count)),
        )


def import_legacy_csv(csv_path: Path, device_id: str = 'legacy-csv') -> int:
    csv_path = csv_path.resolve()
    if not csv_path.exists() or _already_imported('legacy_csv', csv_path):
        return 0

    df = pd.read_csv(csv_path)
    expected = {'valor_analogico', 'voltaje', 'calidad_aire'}
    if not expected.issubset(set(df.columns)):
        raise ValueError(f'CSV no compatible: {csv_path}')

    imported = 0
    for _, row in df.iterrows():
        payload = UnifiedReadingIn(
            device_id=device_id,
            ao=int(row['valor_analogico']),
            voltage=None if pd.isna(row['voltaje']) else float(row['voltaje']),
            quality_label=None if pd.isna(row['calidad_aire']) else str(row['calidad_aire']),
            source='legacy_csv',
        )
        insert_reading(payload)
        imported += 1

    _mark_imported('legacy_csv', csv_path, imported)
    return imported


def import_legacy_sqlite(db_path: Path) -> int:
    db_path = db_path.resolve()
    if not db_path.exists() or _already_imported('legacy_sqlite', db_path):
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            'SELECT ts, device_id, ao, do FROM readings ORDER BY id ASC'
        ).fetchall()
    finally:
        conn.close()

    imported = 0
    for row in rows:
        payload = UnifiedReadingIn(
            device_id=row['device_id'] or DEFAULT_DEVICE_ID,
            ao=int(row['ao']),
            do_value=bool(row['do']) if row['do'] is not None else None,
            quality_label=infer_quality_label(int(row['ao'])),
            source='migration',
            ts=datetime.fromisoformat(row['ts']),
        )
        insert_reading(payload)
        imported += 1

    _mark_imported('legacy_sqlite', db_path, imported)
    return imported


def import_known_legacy_files(base_dir: Path) -> dict[str, int]:
    candidates = {
        'legacy_csv': base_dir / 'legacy_inputs' / 'datos_calidad_aire.csv',
        'legacy_sqlite': base_dir / 'legacy_inputs' / 'mq135.db',
    }
    results = {'legacy_csv': 0, 'legacy_sqlite': 0}
    if candidates['legacy_csv'].exists():
        results['legacy_csv'] = import_legacy_csv(candidates['legacy_csv'])
    if candidates['legacy_sqlite'].exists():
        results['legacy_sqlite'] = import_legacy_sqlite(candidates['legacy_sqlite'])
    return results
