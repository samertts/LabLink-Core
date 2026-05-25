from __future__ import annotations

import json
import platform
from datetime import datetime, timezone

from app.compatibility.validator import validate_platform
from app.settings.paths import LOGS_DIR
from app.validation.startup import validate_runtime


def write_diagnostics() -> str:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "compatibility": validate_platform().__dict__,
        "runtime_validation": validate_runtime().__dict__,
    }
    out = LOGS_DIR / "diagnostics.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(out)
