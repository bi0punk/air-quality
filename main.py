# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
# Agrega este import junto a los demás:
from fastapi.responses import HTMLResponse

app = FastAPI(title="MQ135 Collector")

# CORS opcional (por si consultas desde un navegador)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajusta en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MQ135Reading(BaseModel):
    device_id: str = Field(..., examples=["mq135-uno-1"])
    ao: int = Field(..., ge=0, le=1023, examples=[512])
    do: bool = Field(..., examples=[True])

class MQ135Stored(MQ135Reading):
    ts: datetime

# Simple “DB” en memoria
DB: List[MQ135Stored] = []

@app.post("/api/mq135", response_model=MQ135Stored)
def ingest_reading(reading: MQ135Reading):
    stored = MQ135Stored(**reading.dict(), ts=datetime.utcnow())
    DB.append(stored)
    return stored

@app.get("/api/mq135", response_model=List[MQ135Stored])
def list_readings(limit: Optional[int] = 100):
    return DB[-limit:] if limit else DB

@app.get("/api/mq135/latest", response_model=MQ135Stored)
def latest_reading():
    if not DB:
        raise HTTPException(status_code=404, detail="No hay lecturas aún")
    return DB[-1]

# (Opcional) mini dashboard HTML

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    html = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="Cache-Control" content="no-store" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MQ-135 • Panel</title>
  <style>
    :root{
      --bg:#0e1013; --card:#151922; --muted:#778; --text:#e6e8ef;
      --accent:#51d1f6; --ok:#56d364; --warn:#f7c948; --bad:#ff6b6b;
      --grid:#202635; --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      --sans: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial, sans-serif;
    }
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.35}
    .wrap{max-width:1100px;margin:32px auto;padding:0 16px}
    header{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:18px}
    h1{margin:0;font-size:28px;letter-spacing:.2px}
    .sub{color:var(--muted);font-size:14px}
    .grid{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:16px}
    .card{background:linear-gradient(180deg,#161b25 0%, #121722 100%);border:1px solid #22283a;border-radius:14px;padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.35)}
    .title{color:var(--muted);font-size:13px;margin:0 0 8px 0;letter-spacing:.4px;text-transform:uppercase}
    .big{
      display:flex;align-items:center;justify-content:space-between;gap:16px
    }
    .big .value{font-family:var(--mono);font-size:64px;font-weight:700;letter-spacing:1px}
    .big .units{font-family:var(--mono);font-size:16px;color:var(--muted)}
    .kv{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:8px}
    .kv .k{font-size:12px;color:var(--muted)}
    .kv .v{font-family:var(--mono);font-size:18px}
    .badge{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:6px 12px;font-weight:600;border:1px solid #2a3246;background:#121722}
    .badge.ok{border-color:#254b32;color:#b7f7c0}
    .badge.bad{border-color:#4a1d1d;color:#ffb3b3}
    .badge.warn{border-color:#584a1a;color:#ffe7a3}

    .table-card{margin-top:10px}
    table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13px}
    thead th{color:#9aa2b1;text-align:left;font-weight:600;padding:10px;border-bottom:1px solid #2a3042;background:#171c27;position:sticky;top:0}
    tbody td{padding:10px;border-bottom:1px dashed #232a3b}
    tbody tr:nth-child(even){background:#131825}
    .pill{padding:2px 8px;border-radius:10px;border:1px solid #2a3042}
    .pill.high{border-color:#4a1d1d;color:#ffb3b3}
    .pill.low{border-color:#254b32;color:#b7f7c0}

    .footer{color:var(--muted);font-size:12px;margin-top:14px}
    .micro{font-family:var(--mono);font-size:12px;color:#9aa2b1}
    .spark{height:42px;width:100%;display:block}
    canvas{width:100%;height:42px}
    @media (max-width:900px){ .grid{grid-template-columns:1fr} .big .value{font-size:48px} }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>MQ-135 • Panel de Calidad de Aire</h1>
        <div class="sub">Estilo técnico / científico · Actualización automática</div>
      </div>
      <div class="micro" id="clock">--:--:--</div>
    </header>

    <section class="grid">
      <div class="card">
        <div class="title">Última medición</div>
        <div class="big">
          <div>
            <div class="value" id="last-ao">--</div>
            <div class="units">AO (0–1023)</div>
          </div>
          <div id="do-badge" class="badge">DO: --</div>
        </div>
        <div class="kv">
          <div>
            <div class="k">Timestamp</div>
            <div class="v" id="last-ts">--</div>
          </div>
          <div>
            <div class="k">Dispositivo</div>
            <div class="v" id="last-dev">--</div>
          </div>
          <div>
            <div class="k">Calidad estimada</div>
            <div class="v" id="last-qual">--</div>
          </div>
        </div>
        <div class="spark"><canvas id="spark"></canvas></div>
      </div>

      <div class="card">
        <div class="title">Estado</div>
        <div class="kv">
          <div>
            <div class="k">Lecturas almacenadas</div>
            <div class="v" id="count">--</div>
          </div>
          <div>
            <div class="k">Promedio (últimas 10)</div>
            <div class="v" id="avg10">--</div>
          </div>
          <div>
            <div class="k">Máximo (últimas 10)</div>
            <div class="v" id="max10">--</div>
          </div>
        </div>
      </div>
    </section>

    <section class="card table-card">
      <div class="title">Últimas 10 lecturas</div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Timestamp (UTC)</th>
            <th>Device</th>
            <th>AO</th>
            <th>DO</th>
          </tr>
        </thead>
        <tbody id="rows">
          <tr><td colspan="5">Sin datos</td></tr>
        </tbody>
      </table>
      <div class="footer">Fuente: /api/mq135 &nbsp;·&nbsp; Actualiza cada 2 s</div>
    </section>
  </div>

<script>
const fmtTime = (iso) => {
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat('es-CL', {
      dateStyle: 'short', timeStyle: 'medium'
    }).format(d);
  } catch { return iso; }
};

function qualityLabel(ao){
  if (ao === null || ao === undefined) return "--";
  if (ao < 200) return "Muy buena";
  if (ao < 400) return "Aceptable";
  if (ao < 700) return "Mala (ventilar)";
  return "Muy mala / Humo";
}

function updateBadge(el, val){
  el.textContent = "DO: " + (val ? "HIGH" : "LOW");
  el.classList.remove("ok","bad","warn");
  if (val) el.classList.add("bad"); else el.classList.add("ok");
}

// simple sparkline
const spark = document.getElementById('spark');
const ctx = spark.getContext('2d');
let sparkData = [];

function drawSpark(data){
  const W = spark.width, H = spark.height;
  ctx.clearRect(0,0,W,H);
  if (!data.length) return;
  const max = Math.max(...data), min = Math.min(...data);
  const pad = 4;
  ctx.beginPath();
  data.forEach((v,i)=>{
    const x = pad + (i*(W-2*pad)/(data.length-1||1));
    const y = H - pad - ( (v-min) / ((max-min)||1) )*(H-2*pad);
    if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  });
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#51d1f6";
  ctx.stroke();
}

async function fetchLatest(){
  const r = await fetch('/api/mq135/latest', {cache:'no-store'});
  if(!r.ok) return null;
  return await r.json();
}
async function fetchLast10(){
  const r = await fetch('/api/mq135?limit=10', {cache:'no-store'});
  if(!r.ok) return [];
  return await r.json();
}

function renderTable(items){
  const tbody = document.getElementById('rows');
  if (!items.length){ tbody.innerHTML = '<tr><td colspan="5">Sin datos</td></tr>'; return; }
  let i = 0;
  tbody.innerHTML = items.map(it=>{
    i++;
    return `<tr>
      <td>${i}</td>
      <td>${fmtTime(it.ts)}</td>
      <td>${it.device_id}</td>
      <td>${it.ao}</td>
      <td><span class="pill ${it.do ? 'high' : 'low'}">${it.do ? 'HIGH' : 'LOW'}</span></td>
    </tr>`;
  }).join('');
}

function stats(items){
  if(!items.length) return {avg:'--',max:'--'};
  const arr = items.map(x=>x.ao);
  const avg = Math.round(arr.reduce((a,b)=>a+b,0)/arr.length);
  const max = Math.max(...arr);
  return {avg, max};
}

async function tick(){
  try{
    const [latest, list] = await Promise.all([fetchLatest(), fetchLast10()]);
    document.getElementById('count').textContent = String(list.length ? list.length : (latest?1:0));
    if (latest){
      document.getElementById('last-ao').textContent = latest.ao;
      document.getElementById('last-ts').textContent = fmtTime(latest.ts);
      document.getElementById('last-dev').textContent = latest.device_id;
      document.getElementById('last-qual').textContent = qualityLabel(latest.ao);
      updateBadge(document.getElementById('do-badge'), latest.do);
    }
    // sparkline con historial (usa últimas 10 invertidas para ver secuencia temporal)
    const data = list.length ? list.map(x=>x.ao) : (latest ? [latest.ao] : []);
    sparkData = data.slice(-30); // guarda un histórico pequeño
    drawSpark(sparkData);

    // tabla (mostrar del más reciente al más antiguo)
    renderTable(list);
    const st = stats(list);
    document.getElementById('avg10').textContent = st.avg;
    document.getElementById('max10').textContent = st.max;
  }catch(e){
    console.error(e);
  }
}

function runClock(){
  const el = document.getElementById('clock');
  setInterval(()=>{
    const d = new Date();
    el.textContent = d.toLocaleString('es-CL', {hour12:false});
  }, 500);
}

function resizeCanvas(){
  // ajustar tamaño físico al CSS para alta DPI
  const rect = spark.getBoundingClientRect();
  spark.width = rect.width * window.devicePixelRatio;
  spark.height = rect.height * window.devicePixelRatio;
  drawSpark(sparkData);
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();
runClock();
tick();
setInterval(tick, 2000);
</script>
</body>
</html>
    """
    return HTMLResponse(html)

