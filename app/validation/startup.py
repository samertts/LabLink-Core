from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Literal


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


def validate_runtime(profile: Literal["core", "desktop"] = "desktop") -> ValidationResult:
    errors: list[str] = []
    modules = ["fastapi", "uvicorn", "pydantic", "httpx"]
    if profile == "desktop":
        modules.append("PySide6")

    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as exc:  # pragma: no cover
            errors.append(f"missing_dependency:{mod}:{exc}")
    return ValidationResult(ok=not errors, errors=errors)
