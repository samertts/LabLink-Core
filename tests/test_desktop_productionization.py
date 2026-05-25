from __future__ import annotations

import json

from app.recovery.diagnostics import write_diagnostics
from app.recovery.manager import ensure_runtime_files
from app.settings.paths import LOGS_DIR, RUNTIME_CONFIG, RUNTIME_DB


def test_runtime_repair_creates_core_files() -> None:
    report = ensure_runtime_files()
    assert RUNTIME_CONFIG.exists()
    assert RUNTIME_DB.exists()
    assert isinstance(report.repaired, list)


def test_diagnostics_file_generation() -> None:
    output = write_diagnostics()
    data = json.loads((LOGS_DIR / "diagnostics.json").read_text(encoding="utf-8"))
    assert output.endswith("diagnostics.json")
    assert "runtime_validation" in data
