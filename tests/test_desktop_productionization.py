from __future__ import annotations

import json

from app.recovery.diagnostics import write_diagnostics
from app.recovery.manager import ensure_runtime_files
from app.settings.paths import LOGS_DIR, RUNTIME_CONFIG, RUNTIME_DB
from app.validation.startup import validate_runtime


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


def test_core_profile_validation_passes_without_pyside() -> None:
    result = validate_runtime(profile="core")
    assert result.ok
