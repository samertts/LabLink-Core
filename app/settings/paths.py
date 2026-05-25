from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = PROJECT_ROOT / "storage"
DATA_DIR = STORAGE_ROOT / "data"
BACKUPS_DIR = STORAGE_ROOT / "backups"
EXPORTS_DIR = STORAGE_ROOT / "exports"
LOGS_DIR = STORAGE_ROOT / "logs"
TEMP_DIR = STORAGE_ROOT / "temp"
RUNTIME_DB = DATA_DIR / "lablink.db"
RUNTIME_CONFIG = STORAGE_ROOT / "runtime_config.json"

REQUIRED_DIRS = [
    STORAGE_ROOT,
    DATA_DIR,
    BACKUPS_DIR,
    EXPORTS_DIR,
    LOGS_DIR,
    TEMP_DIR,
]
