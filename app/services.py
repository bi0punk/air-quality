from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from .config import AO_ALERT_THRESHOLD, DEFAULT_DEVICE_ID
from .db import connection


CSV_FIELDNAMES = [
    'id', 'ts', 'device_id', 'source', 'ao', 'do_value', 'voltage', 'quality_label',
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_quality_label(ao: int) -> str:
    if ao < 300:
        return 'Muy buena'
    if ao < 450:
        return 'Aceptable'
    if ao < 650:
        return 'Mala (ventilar)'
    return 'Muy mala / posible humo o gas'


def infer_do_value(ao: int, provided: Optional[bool]) -> Optional[bool]:
    if provided is not None:
        return provided
    return ao >= AO_ALERT_THRESHOLD


def _normalize_ts(raw_ts: Any) -> str:
    if not raw_ts:
        return utc_now_iso()
    try:
        if isinstance(raw_ts, datetime):
            dt = raw_ts
        else:
            dt = datetime.fromisoformat(str(raw_ts))
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return utc_now_iso()


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un dict de payload (unificado o legacy) a formato de base de datos."""
    ao_raw = payload.get('ao')
    if ao_raw is None:
        ao_raw = payload.get('valor_analogico', 0)
    ao = int(float(ao_raw or 0))

    quality_label = payload.get('quality_label') or payload.get('calidad_aire')
    if quality_label is not None and not isinstance(quality_label, str):
        quality_label = str(quality_label)
    if not quality_label:
        quality_label = infer_quality_label(ao)

    voltage = payload.get('voltage')
    if voltage is None:
        voltage = payload.get('voltaje')

    do_value = infer_do_value(ao, payload.get('do_value'))
    device_id = str(payload.get('device_id') or DEFAULT_DEVICE_ID).strip()

    return {
        'ts': _normalize_ts(payload.get('ts')),
        'device_id': device_id,
        'ao': ao,
        'do_value': None if do_value is None else int(bool(do_value)),
        'voltage': voltage,
        'quality_label': quality_label,
        'source': payload.get('source', 'api'),
    }


def insert_reading(payload: dict[str, Any]) -> int:
    """Inserta una lectura desde un dict y devuelve su id."""
    data = normalize_payload(payload)
    with connection() as conn:
        cur = conn.execute(
            '''
            INSERT INTO readings (ts, device_id, ao, do_value, voltage, quality_label, source)
            VALUES (:ts, :device_id, :ao, :do_value, :voltage, :quality_label, :source)
            ''',
            data,
        )
        return int(cur.lastrowid)


def fetch_by_id(reading_id: int) -> Optional[dict[str, Any]]:
    with connection() as conn:
        row = conn.execute(
            '''
            SELECT id, ts, device_id, ao, do_value, voltage, quality_label, source
            FROM readings
            WHERE id = ?
            ''',
            (int(reading_id),),
        ).fetchone()
        return dict(row) if row else None


def fetch_latest() -> Optional[dict[str, Any]]:
    with connection() as conn:
        row = conn.execute(
            '''
            SELECT id, ts, device_id, ao, do_value, voltage, quality_label, source
            FROM readings
            ORDER BY id DESC
            LIMIT 1
            '''
        ).fetchone()
        return dict(row) if row else None


def fetch_readings(limit: int = 100, device_id: Optional[str] = None) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 5000))
    query = (
        'SELECT id, ts, device_id, ao, do_value, voltage, quality_label, source '
        'FROM readings '
    )
    params: list[Any] = []
    if device_id:
        query += 'WHERE device_id = ? '
        params.append(device_id)
    query += 'ORDER BY id DESC LIMIT ?'
    params.append(limit)
    with connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows][::-1]


def fetch_stats(window: int = 10) -> dict[str, Any]:
    window = max(1, min(int(window), 1000))
    with connection() as conn:
        total = int(conn.execute('SELECT COUNT(*) AS c FROM readings').fetchone()['c'])
        latest = conn.execute(
            'SELECT ts, device_id, ao FROM readings ORDER BY id DESC LIMIT 1'
        ).fetchone()
        agg = conn.execute(
            '''
            SELECT AVG(ao) AS avg_ao, MIN(ao) AS min_ao, MAX(ao) AS max_ao
            FROM (
                SELECT ao FROM readings ORDER BY id DESC LIMIT ?
            ) t
            ''',
            (window,),
        ).fetchone()
    latest_ao = int(latest['ao']) if latest else 0
    return {
        'total': total,
        'window': window,
        'avg_ao': float(agg['avg_ao']) if agg and agg['avg_ao'] is not None else 0.0,
        'min_ao': int(agg['min_ao']) if agg and agg['min_ao'] is not None else 0,
        'max_ao': int(agg['max_ao']) if agg and agg['max_ao'] is not None else 0,
        'latest_device_id': latest['device_id'] if latest else None,
        'latest_ts': latest['ts'] if latest else None,
        'alert_active': latest_ao >= AO_ALERT_THRESHOLD,
    }


def fetch_device_breakdown(limit: int = 1000) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 10000))
    with connection() as conn:
        rows = conn.execute(
            '''
            SELECT device_id, COUNT(*) AS count, ROUND(AVG(ao), 2) AS avg_ao, MAX(ao) AS max_ao
            FROM (
                SELECT device_id, ao FROM readings ORDER BY id DESC LIMIT ?
            ) t
            GROUP BY device_id
            ORDER BY count DESC, device_id ASC
            ''',
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def rows_to_csv(rows: Iterable[dict[str, Any]]) -> str:
    """Serializa lecturas a texto CSV listo para streaming."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDNAMES, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()