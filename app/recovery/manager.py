from __future__ import annotations

import json
from dataclasses import dataclass

from app.settings.paths import REQUIRED_DIRS, RUNTIME_CONFIG, RUNTIME_DB


@dataclass
class RepairReport:
    repaired: list[str]
    warnings: list[str]


def ensure_runtime_files() -> RepairReport:
    from app.storage.db import InMemoryDB
    from app.settings.paths import DATA_DIR

    repaired: list[str] = []
    warnings: list[str] = []

    for d in REQUIRED_DIRS:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            repaired.append(f"created_dir:{d}")

    if not RUNTIME_CONFIG.exists():
        RUNTIME_CONFIG.write_text(json.dumps({"api_host": "127.0.0.1", "api_port": 8000}, indent=2), encoding="utf-8")
        repaired.append(f"created_file:{RUNTIME_CONFIG}")

    db_path = str(DATA_DIR / "lablink.db")
    db = InMemoryDB(db_path=db_path)
    if not RUNTIME_DB.exists():
        repaired.append(f"created_file:{RUNTIME_DB}")

    if not db.integrity_check():
        warnings.append("database_integrity_warning:integrity check failed")

    db.close()
    return RepairReport(repaired=repaired, warnings=warnings)
