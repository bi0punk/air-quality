from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path
import csv

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .config import APP_TITLE, BASE_DIR, DEFAULT_DEVICE_ID, IMPORT_ON_STARTUP
from .db import init_db
from .legacy_import import import_known_legacy_files
from .schemas import LegacyCSVIn, MQ135In, ReadingOut, StatsOut, UnifiedReadingIn
from .services import (
    fetch_device_breakdown,
    fetch_latest,
    fetch_readings,
    fetch_stats,
    infer_quality_label,
    insert_reading,
    rows_to_csv_rows,
)

app = FastAPI(title=APP_TITLE, version='2.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

templates = Jinja2Templates(directory=str(BASE_DIR / 'app' / 'templates'))


@app.on_event('startup')
def on_startup() -> None:
    init_db()
    if IMPORT_ON_STARTUP:
        try:
            results = import_known_legacy_files(BASE_DIR)
            print(f'[startup] import legacy results: {results}')
        except Exception as exc:
            print(f'[startup] legacy import error: {exc}')


@app.get('/health')
def health() -> dict:
    return {'status': 'ok', 'service': APP_TITLE}


@app.post('/api/readings', response_model=ReadingOut)
def create_reading(payload: UnifiedReadingIn):
    new_id = insert_reading(payload)
    row = fetch_latest()
    if not row or row['id'] != new_id:
        raise HTTPException(status_code=500, detail='No se pudo recuperar la lectura guardada')
    return row


@app.post('/api/mq135', response_model=ReadingOut)
def create_mq135(payload: MQ135In):
    unified = UnifiedReadingIn(
        device_id=payload.device_id,
        ao=payload.ao,
        do_value=payload.do,
        quality_label=infer_quality_label(payload.ao),
        source='mq135_api',
    )
    new_id = insert_reading(unified)
    row = fetch_latest()
    if not row or row['id'] != new_id:
        raise HTTPException(status_code=500, detail='No se pudo recuperar la lectura guardada')
    return row


@app.post('/data')
def create_legacy(payload: LegacyCSVIn):
    unified = UnifiedReadingIn(
        device_id=DEFAULT_DEVICE_ID,
        ao=payload.valor_analogico,
        voltage=payload.voltaje,
        quality_label=payload.calidad_aire or infer_quality_label(payload.valor_analogico),
        source='legacy_csv',
    )
    insert_reading(unified)
    return JSONResponse({'message': 'Datos guardados con éxito', 'compat_mode': 'legacy_flask'})


@app.get('/api/readings', response_model=list[ReadingOut])
def list_readings(
    limit: int = Query(default=100, ge=1, le=5000),
    device_id: str | None = Query(default=None),
):
    return fetch_readings(limit=limit, device_id=device_id)


@app.get('/api/readings/latest', response_model=ReadingOut)
def latest_reading():
    row = fetch_latest()
    if not row:
        raise HTTPException(status_code=404, detail='No hay lecturas aún')
    return row


@app.get('/api/stats', response_model=StatsOut)
def stats(window: int = Query(default=10, ge=1, le=1000)):
    return fetch_stats(window)


@app.get('/api/devices')
def devices(limit: int = Query(default=1000, ge=1, le=10000)):
    return fetch_device_breakdown(limit)


@app.get('/api/export/csv')
def export_csv(limit: int = Query(default=10000, ge=1, le=50000)):
    rows = fetch_readings(limit=limit)
    csv_rows = rows_to_csv_rows(rows)
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=['id', 'ts', 'device_id', 'ao', 'do_value', 'voltaje', 'calidad_aire', 'source'],
    )
    writer.writeheader()
    writer.writerows(csv_rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename=air_quality_export.csv'},
    )


@app.get('/', response_class=HTMLResponse)
@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse('dashboard.html', {'request': request})


@app.get('/api/info', response_class=PlainTextResponse)
def info() -> str:
    return (
        'Air Quality Fusion API\n'
        'Compatibilidad: POST /data (Flask legacy), POST /api/mq135, POST /api/readings\n'
        'Dashboard: /dashboard\n'
        'Salud: /health\n'
    )
