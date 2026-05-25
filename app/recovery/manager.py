from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from app.settings.paths import REQUIRED_DIRS, RUNTIME_CONFIG, RUNTIME_DB


@dataclass
class RepairReport:
    repaired: list[str]
    warnings: list[str]


def ensure_runtime_files() -> RepairReport:
    repaired: list[str] = []
    warnings: list[str] = []

    for d in REQUIRED_DIRS:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            repaired.append(f"created_dir:{d}")

    if not RUNTIME_CONFIG.exists():
        RUNTIME_CONFIG.write_text(json.dumps({"api_host": "127.0.0.1", "api_port": 8000}, indent=2), encoding="utf-8")
        repaired.append(f"created_file:{RUNTIME_CONFIG}")

    if not RUNTIME_DB.exists():
        conn = sqlite3.connect(RUNTIME_DB)
        conn.execute("CREATE TABLE IF NOT EXISTS startup_checks (id INTEGER PRIMARY KEY, checked_at TEXT NOT NULL)")
        conn.commit()
        conn.close()
        repaired.append(f"created_file:{RUNTIME_DB}")

    try:
        conn = sqlite3.connect(RUNTIME_DB)
        conn.execute("PRAGMA integrity_check")
        conn.close()
    except sqlite3.DatabaseError as exc:
        warnings.append(f"database_integrity_warning:{exc}")

    return RepairReport(repaired=repaired, warnings=warnings)
