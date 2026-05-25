from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


def validate_runtime() -> ValidationResult:
    errors: list[str] = []
    for mod in ("fastapi", "uvicorn", "pydantic", "httpx", "PySide6"):
        try:
            importlib.import_module(mod)
        except Exception as exc:  # pragma: no cover
            errors.append(f"missing_dependency:{mod}:{exc}")
    return ValidationResult(ok=not errors, errors=errors)
