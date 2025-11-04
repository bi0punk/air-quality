# main.py
from datetime import datetime, timezone
from typing import List, Optional

import sqlite3
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

DB_PATH = "mq135.db"

# ------------------------ DB helpers ------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,               -- ISO8601 UTC
                device_id TEXT NOT NULL,
                ao INTEGER NOT NULL,
                do INTEGER NOT NULL             -- 0/1
            )
            """
        )
        conn.commit()

init_db()

def insert_reading(device_id: str, ao: int, do: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO readings (ts, device_id, ao, do) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), device_id, ao, 1 if do else 0),
        )
        conn.commit()

def fetch_last_n(n: int) -> List[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT ts, device_id, ao, do FROM readings ORDER BY id DESC LIMIT ?",
            (n,),
        )
        return cur.fetchall()

def fetch_latest() -> Optional[sqlite3.Row]:
    rows = fetch_last_n(1)
    return rows[0] if rows else None

def fetch_stats(n: int = 10):
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM readings").fetchone()["c"]
        cur = conn.execute(
            """
            SELECT AVG(ao) AS avg_ao, MAX(ao) AS max_ao
            FROM (SELECT ao FROM readings ORDER BY id DESC LIMIT ?)
            """,
            (n,),
        )
        row = cur.fetchone()
        return {
            "count": int(total),
            "avg_last_n": int(row["avg_ao"]) if row["avg_ao"] is not None else 0,
            "max_last_n": int(row["max_ao"]) if row["max_ao"] is not None else 0,
            "window": n,
        }

# ------------------------ API ------------------------
app = FastAPI(title="MQ135 Collector")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ajusta en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

class MQ135Reading(BaseModel):
    device_id: str = Field(..., examples=["mq135-uno-1"])
    ao: int = Field(..., ge=0, le=1023, examples=[512])
    do: bool = Field(..., examples=[True])

class MQ135Stored(MQ135Reading):
    ts: datetime

def row_to_model(row: sqlite3.Row) -> MQ135Stored:
    return MQ135Stored(
        device_id=row["device_id"],
        ao=int(row["ao"]),
        do=bool(row["do"]),
        ts=datetime.fromisoformat(row["ts"]),
    )

@app.post("/api/mq135", response_model=MQ135Stored)
def ingest_reading(reading: MQ135Reading):
    insert_reading(reading.device_id, reading.ao, reading.do)
    latest = fetch_latest()
    return row_to_model(latest)

@app.get("/api/mq135", response_model=List[MQ135Stored])
def list_readings(limit: Optional[int] = 100):
    rows = fetch_last_n(limit or 100)
    return [row_to_model(r) for r in rows][::-1]  # ascendente para tablas/gráficas

@app.get("/api/mq135/latest", response_model=MQ135Stored)
def latest_reading():
    row = fetch_latest()
    if not row:
        raise HTTPException(status_code=404, detail="No hay lecturas aún")
    return row_to_model(row)

@app.get("/api/mq135/stats")
def stats(limit: int = 10):
    return fetch_stats(limit)

# Dashboard (plantilla)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})