from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass
class CompatibilityResult:
    supported: bool
    details: str


def validate_platform() -> CompatibilityResult:
    system = platform.system().lower()
    if system == "windows":
        return CompatibilityResult(supported=True, details="Native Windows runtime")
    return CompatibilityResult(supported=True, details=f"Non-Windows runtime detected ({system}); desktop shell still available for validation")
