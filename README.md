# Air Quality Fusion API

Proyecto unificado y mejorado a partir de dos bases existentes:

- **Proyecto 1**: Flask + CSV (`POST /data`) para guardar `valor_analogico`, `voltaje`, `calidad_aire`.
- **Proyecto 2**: FastAPI + SQLite + dashboard (`POST /api/mq135`) para guardar `device_id`, `ao`, `do`.

La nueva versión consolida ambos enfoques en un solo backend moderno, manteniendo compatibilidad con el formato antiguo y agregando una base más sólida para producción liviana.

## Qué se mejoró

1. **Unificación real del modelo de datos**
   - Una sola tabla `readings`.
   - Campos soportados: `device_id`, `ao`, `do_value`, `voltage`, `quality_label`, `source`, `ts`.

2. **Compatibilidad hacia atrás**
   - Sigue aceptando el endpoint legado `POST /data`.
   - Sigue aceptando `POST /api/mq135`.
   - Además agrega `POST /api/readings` como endpoint canónico.

3. **Persistencia mejorada**
   - SQLite como almacenamiento principal.
   - Exportación CSV on-demand.
   - Importador de datos antiguos (`datos_calidad_aire.csv` y `mq135.db`).

4. **Dashboard mejorado**
   - Última lectura.
   - Estado de alerta.
   - Histórico de AO.
   - Tabla de últimas lecturas.
   - Resumen por dispositivo.

5. **Hardening básico**
   - Host configurable.
   - Validaciones con Pydantic.
   - Índices SQLite.
   - Importación idempotente con `import_registry`.

## Hallazgos del análisis de los proyectos originales

### Proyecto 1 (Flask + CSV)

**Fortalezas**
- Muy simple para integrar desde un microcontrolador.
- Formato de payload claro.
- CSV fácil de inspeccionar.

**Debilidades**
- Host IP hardcodeado.
- Sin dashboard.
- Sin estadísticas.
- Sin control de crecimiento del CSV.
- Sin separación por dispositivo.
- Sin timestamps explícitos en cada fila.

### Proyecto 2 (FastAPI + SQLite + Dashboard)

**Fortalezas**
- Mucho mejor base técnica.
- Persistencia robusta.
- Dashboard útil.
- Endpoints más limpios.

**Debilidades**
- Esquema limitado: no guarda `voltaje` ni `calidad_aire` textual.
- No es compatible con el formato Flask antiguo.
- No exporta CSV.
- Estructura aún muy monolítica.

## Arquitectura final

```text
ESP32 / cliente HTTP
   ├── POST /data          (payload legacy Flask)
   ├── POST /api/mq135     (payload MQ135 actual)
   └── POST /api/readings  (payload unificado)

FastAPI
   ├── Validación Pydantic
   ├── Servicio de normalización
   ├── Persistencia SQLite
   ├── Importador legacy
   ├── Exportador CSV
   └── Dashboard HTML

SQLite
   ├── readings
   └── import_registry
```

## Estructura

```text
air_quality_unificado_mejorado/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── legacy_import.py
│   ├── main.py
│   ├── schemas.py
│   ├── services.py
│   └── templates/
│       └── dashboard.html
├── data/
├── legacy_inputs/
│   ├── datos_calidad_aire.csv
│   └── mq135.db
├── import_legacy.py
├── requirements.txt
├── run.sh
└── README.md
```

## Instalación

```bash
cd air_quality_unificado_mejorado
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
./run.sh
```

Quedará disponible en:

- Dashboard: `http://127.0.0.1:8000/dashboard`
- Salud: `http://127.0.0.1:8000/health`
- Info: `http://127.0.0.1:8000/api/info`

## Importación automática de los proyectos antiguos

En el arranque, el sistema intenta importar automáticamente:

- `legacy_inputs/datos_calidad_aire.csv`
- `legacy_inputs/mq135.db`

La importación es **idempotente**: no vuelve a importar el mismo archivo si ya fue registrado.

## Endpoints

### 1) Legacy Flask

```bash
curl -X POST http://127.0.0.1:8000/data \
  -H 'Content-Type: application/json' \
  -d '{
    "valor_analogico": 333,
    "voltaje": 0.27,
    "calidad_aire": "Buena"
  }'
```

### 2) Compatibilidad MQ135 actual

```bash
curl -X POST http://127.0.0.1:8000/api/mq135 \
  -H 'Content-Type: application/json' \
  -d '{
    "device_id": "mq135-uno-1",
    "ao": 512,
    "do": true
  }'
```

### 3) Endpoint unificado recomendado

```bash
curl -X POST http://127.0.0.1:8000/api/readings \
  -H 'Content-Type: application/json' \
  -d '{
    "device_id": "sensor-lab-01",
    "ao": 421,
    "do_value": false,
    "voltage": 0.33,
    "quality_label": "Aceptable",
    "source": "manual"
  }'
```

### 4) Consultar lecturas

```bash
curl 'http://127.0.0.1:8000/api/readings?limit=20'
```

### 5) Última lectura

```bash
curl 'http://127.0.0.1:8000/api/readings/latest'
```

### 6) Estadísticas

```bash
curl 'http://127.0.0.1:8000/api/stats?window=20'
```

### 7) Exportar CSV

```bash
curl -OJ 'http://127.0.0.1:8000/api/export/csv?limit=10000'
```

## Importación manual

```bash
python3 import_legacy.py --csv ./legacy_inputs/datos_calidad_aire.csv --sqlite ./legacy_inputs/mq135.db
```

## Siguientes mejoras naturales

1. Autenticación para endpoints de ingestión.
2. Retención de datos y particionado lógico.
3. Alertas por Telegram/Email si `ao` supera umbral.
4. WebSocket o SSE para actualización en tiempo real sin polling.
5. Dockerización con volumen persistente.
6. Soporte multi-sensor real con calibración por dispositivo.
7. Conversión de AO a ppm si defines curva/calibración real del sensor.

## Nota técnica importante

El valor `AO` del MQ-135 **no equivale directamente** a una medida ambiental certificada sin calibración. Este proyecto lo trata correctamente como una **señal relativa** útil para tendencias, alertas internas y comparación entre lecturas del mismo dispositivo.
