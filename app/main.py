from __future__ import annotations

import csv
import io
import os
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .config import APP_TITLE, BASE_DIR, DEFAULT_DEVICE_ID, IMPORT_ON_STARTUP, DB_PATH
from .services import (
    fetch_latest as svc_fetch_latest,
    fetch_readings as svc_fetch_readings,
    fetch_stats as svc_fetch_stats,
    fetch_device_breakdown as svc_fetch_device_breakdown,
    insert_reading as svc_insert_reading,
    rows_to_csv_rows as svc_rows_to_csv_rows,
    normalize_payload as svc_normalize_payload,
)
from .schemas import (
    UnifiedReadingIn,
    ReadingOut,
    ReadingListItem,
    LegacyCSVIn,
    MQ135In,
    QualityLabel,
    ReadingSource,
    validate_reading_payload,
    reading_to_dict,
)


app = FastAPI(title="Air Quality Fusion API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Asegurar que la base de datos existe al iniciar
@app.on_event("startup")
def on_startup() -> None:
    # Crear directorio de datos si no existe
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    # Inicializar base de datos
    from .db import init_db
    init_db()
    if IMPORT_ON_STARTUP:
        try:
            from . import services as svc_module
            results = svc_module.import_known_legacy_files(BASE_DIR)
            print(f"[startup] import legacy results: {results}")
        except Exception as exc:
            print(f"[startup] legacy import error: {exc}")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/api/info") 
def info() -> str:
    return "Air Quality Fusion API"


# --- Lecturas unificadas ---

@app.post("/api/readings", response_model=ReadingOut, status_code=200)
def create_reading_unified(payload: UnifiedReadingIn) -> JSONResponse:
    """Endpoint unificado para recibir lecturas."""
    try:
        validate_reading_payload(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    reading_dict = reading_to_dict(payload)
    new_id = svc_insert_reading(reading_dict)
    row = svc_fetch_latest()
    
    if not row:
        raise HTTPException(status_code=404, detail="No hay lecturas")
    
    return JSONResponse({
        "id": row["id"],
        "ts": row.get("ts", ""),
        "quality_label": row.get("quality_label"),
        "ao": row.get("ao"),
        "do_value": row.get("do_value"),
        "voltage": row.get("voltage"),
        "device_id": row.get("device_id"),
    })


# --- Endpoint legado MQ135 ---

@app.post("/api/mq135", response_model=ReadingOut, status_code=201)
def create_reading_mq135(payload: MQ135In) -> JSONResponse:
    """Endpoint legacy para lectores MQ135."""
    try:
        # Convertir a formato unificado
        unified = UnifiedReadingIn(
            device_id=payload.device_id,
            source=ReadingSource.MQ135,
            ao=payload.ao,
            do_value=payload.do,
        )
        validate_reading_payload(unified)
        reading_dict = reading_to_dict(unified)
        new_id = svc_insert_reading(reading_dict)
        row = svc_fetch_latest()
        
        if not row:
            raise HTTPException(status_code=404, detail="No hay lecturas")
        
        return JSONResponse({
            "id": row["id"],
            "ts": row.get("ts", ""),
            "quality_label": row.get("quality_label"),
            "ao": row.get("ao"),
            "do_value": row.get("do_value"),
            "voltage": row.get("voltage"),
            "device_id": row.get("device_id"),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Endpoint legado Flask /data ---

@app.post("/data", response_class=JSONResponse)
def legacy_data_post(payload: LegacyCSVIn) -> JSONResponse:
    """Compatibilidad con Flask /data endpoint.
    
    Accepta JSON con campos: valor_analogico, voltaje, calidad_aire
    """
    try:
        # Validar primero
        validate_reading_payload(payload)
        
        # Convertir a dict para insertar
        reading_dict = reading_to_dict(payload)
        new_id = svc_insert_reading(reading_dict)
        
        return JSONResponse({
            "message": "Datos guardados con éxito", 
            "compat_mode": "legacy_flask"
        })
    except (ValueError, Exception) as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# --- Listado ---

@app.get("/api/readings", response_model=List[ReadingListItem])
def list_readings(
    limit: int = Query(default=100, ge=1, le=5000),
) -> List[Dict]:
    """Listado de lecturas."""
    readings = svc_fetch_readings(limit=limit)
    return [
        {
            "id": r["id"],
            "ts": r.get("ts", ""),
            "device_id": r.get("device_id", ""),
            "ao": r.get("ao"),
            "do_value": r.get("do_value"),
            "voltage": r.get("voltage"),
            "quality_label": r.get("quality_label"),
            "source": ReadingSource(r.get("source", "api")),
        }
        for r in readings
    ]


@app.get("/api/readings/latest", response_model=ReadingOut)
def latest_reading() -> JSONResponse:
    """Última lectura."""
    row = svc_fetch_latest()
    if not row:
        raise HTTPException(status_code=404, detail="No hay lecturas")
    return JSONResponse({
        "id": row["id"],
        "ts": row.get("ts", ""),
        "quality_label": row.get("quality_label"),
        "ao": row.get("ao"),
        "voltage": row.get("voltage"),
    })


# --- Estadísticas ---

@app.get("/api/stats")
def stats(window: int = Query(default=10, ge=1, le=1000)) -> Dict:
    return svc_fetch_stats(window=window)


# --- Desglose ---

@app.get("/api/devices")
def devices(limit: int = Query(default=1000, ge=1, le=10000)) -> Dict:
    return svc_fetch_device_breakdown(limit=limit)


# --- CSV export ---

@app.get("/api/export/csv")
def export_csv(limit: int = Query(default=10000, ge=1, le=50000)) -> StreamingResponse:
    rows = svc_fetch_readings(limit=limit)
    csv_rows = svc_rows_to_csv_rows(rows)
    import io
    import csv as csv_mod
    buffer = io.StringIO()
    writer = csv_mod.DictWriter(
        buffer,
        fieldnames=["id", "ts", "device_id", "source", "ao", "do_value", "voltage", "calidad_aire", "quality_label"]
    )
    writer.writeheader()
    writer.writerows(csv_rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="air_quality_export.csv"'}
    )


# --- Dashboard ---

@app.get("/", response_class=HTMLResponse)
def dashboard_root() -> HTMLResponse:
    from fastapi import Request
    return HTMLResponse("<h1>Dashboard Air Quality</h1><p>Panel de control</p>")

@app.get("/dashboard", include_in_schema=False)
def dashboard_redirect() -> HTMLResponse:
    from fastapi import Request
    return HTMLResponse("<h1>Dashboard Air Quality</h1><p>Panel de control</h1>")


# --- Debug ---

@app.get("/api/debug/routes")
def debug_routes() -> Dict:
    return {"routes": ["/api/readings", "/api/readings/latest", "/api/stats", "/api/devices", "/api/export/csv"]}
