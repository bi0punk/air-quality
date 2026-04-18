from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv('AIR_QUALITY_DB_PATH', DATA_DIR / 'air_quality.db'))
DEFAULT_DEVICE_ID = os.getenv('AIR_QUALITY_DEFAULT_DEVICE_ID', 'mq135-default')
AO_ALERT_THRESHOLD = int(os.getenv('AIR_QUALITY_AO_ALERT_THRESHOLD', '650'))
IMPORT_ON_STARTUP = os.getenv('AIR_QUALITY_IMPORT_ON_STARTUP', '1').lower() in {'1', 'true', 'yes', 'on'}
HOST = os.getenv('AIR_QUALITY_HOST', '0.0.0.0')
PORT = int(os.getenv('AIR_QUALITY_PORT', '8000'))
APP_TITLE = 'Air Quality Fusion API'
