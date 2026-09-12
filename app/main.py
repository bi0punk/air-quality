from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .config import APP_TITLE, BASE_DIR, DB_PATH, IMPORT_ON_STARTUP
from .schemas import (
    LegacyCSVIn,
    MQ135In,
    ReadingListItem,
    ReadingOut,
    ReadingSource,
    UnifiedReadingIn,
    reading_to_dict,
    validate_reading_payload,
)
from .services import (
    fetch_by_id as svc_fetch_by_id,
    fetch_device_breakdown as svc_fetch_device_breakdown,
    fetch_latest as svc_fetch_latest,
    fetch_readings as svc_fetch_readings,
    fetch_stats as svc_fetch_stats,
    insert_reading as svc_insert_reading,
    rows_to_csv as svc_rows_to_csv,
)

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(BASE_DIR / 'app' / 'templates'))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la DB y la importación legacy al arrancar la app."""
    del app  # no se usan recursos compartidos en el ciclo de vida
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    from .db import init_db
    init_db()
    if IMPORT_ON_STARTUP:
        try:
            from .legacy_import import import_known_legacy_files
            results = import_known_legacy_files(BASE_DIR)
            logger.info('[startup] import legacy results: %s', results)
        except Exception:
            logger.exception('[startup] legacy import error')
    yield


app = FastAPI(title='Air Quality Fusion API', version='2.1.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)


def _row_to_reading_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': row['id'],
        'ts': row.get('ts', ''),
        'device_id': row.get('device_id', ''),
        'ao': row.get('ao'),
        'do_value': row.get('do_value'),
        'voltage': row.get('voltage'),
        'quality_label': row.get('quality_label'),
    }


@app.get('/health')
def health() -> JSONResponse:
    return JSONResponse({'status': 'ok', 'service': APP_TITLE})


@app.get('/api/info', response_class=PlainTextResponse)
def info() -> str:
    return (
        'Air Quality Fusion API\n'
        'Compatibilidad: POST /data (Flask legacy), POST /api/mq135, POST /api/readings\n'
        'Dashboard: /dashboard\n'
        'Salud: /health\n'
    )


# --- Lecturas unificadas ---

@app.post('/api/readings', response_model=ReadingOut, status_code=200)
def create_reading_unified(payload: UnifiedReadingIn) -> dict[str, Any]:
    """Endpoint unificado para recibir lecturas."""
    try:
        validate_reading_payload(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    new_id = svc_insert_reading(reading_to_dict(payload))
    row = svc_fetch_by_id(new_id)
    if not row:
        raise HTTPException(status_code=500, detail='No se pudo recuperar la lectura guardada')
    return _row_to_reading_out(row)


# --- Endpoint legado MQ135 ---

@app.post('/api/mq135', response_model=ReadingOut, status_code=201)
def create_reading_mq135(payload: MQ135In) -> dict[str, Any]:
    """Endpoint legacy para lectores MQ135."""
    unified = UnifiedReadingIn(
        device_id=payload.device_id,
        source=ReadingSource.MQ135,
        ao=payload.ao,
        do_value=payload.do,
    )
    new_id = svc_insert_reading(reading_to_dict(unified))
    row = svc_fetch_by_id(new_id)
    if not row:
        raise HTTPException(status_code=500, detail='No se pudo recuperar la lectura guardada')
    return _row_to_reading_out(row)


# --- Endpoint legado Flask /data ---

@app.post('/data', response_class=JSONResponse)
def legacy_data_post(payload: LegacyCSVIn) -> JSONResponse:
    """Compatibilidad con el endpoint Flask /data (payload legacy)."""
    try:
        validate_reading_payload(payload)
        svc_insert_reading(reading_to_dict(payload))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception('legacy /data insert falló')
        raise HTTPException(status_code=500, detail='Error interno al guardar los datos')

    return JSONResponse({'message': 'Datos guardados con éxito', 'compat_mode': 'legacy_flask'})


# --- Listado ---

@app.get('/api/readings', response_model=list[ReadingListItem])
def list_readings(
    limit: int = Query(default=100, ge=1, le=5000),
    device_id: Optional[str] = Query(default=None),
) -> list[dict[str, Any]]:
    """Listado de lecturas (filtrable por dispositivo, orden cronológico)."""
    readings = svc_fetch_readings(limit=limit, device_id=device_id)
    return [
        {
            'id': r['id'],
            'ts': r.get('ts', ''),
            'device_id': r.get('device_id', ''),
            'ao': r.get('ao'),
            'do_value': r.get('do_value'),
            'voltage': r.get('voltage'),
            'quality_label': r.get('quality_label'),
            'source': ReadingSource(r.get('source', 'api')),
        }
        for r in readings
    ]


@app.get('/api/readings/latest', response_model=ReadingOut)
def latest_reading() -> dict[str, Any]:
    """Última lectura registrada."""
    row = svc_fetch_latest()
    if not row:
        raise HTTPException(status_code=404, detail='No hay lecturas aún')
    return _row_to_reading_out(row)


# --- Estadísticas ---

@app.get('/api/stats')
def stats(window: int = Query(default=10, ge=1, le=1000)) -> dict[str, Any]:
    return svc_fetch_stats(window=window)


# --- Desglose ---

@app.get('/api/devices')
def devices(limit: int = Query(default=1000, ge=1, le=10000)) -> list[dict[str, Any]]:
    return svc_fetch_device_breakdown(limit=limit)


# --- CSV export ---

@app.get('/api/export/csv')
def export_csv(limit: int = Query(default=10000, ge=1, le=50000)) -> StreamingResponse:
    csv_text = svc_rows_to_csv(svc_fetch_readings(limit=limit))
    return StreamingResponse(
        iter([csv_text]),
        media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="air_quality_export.csv"'},
    )


# --- Dashboard ---

@app.get('/', include_in_schema=False)
@app.get('/dashboard', include_in_schema=False)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, 'dashboard.html')