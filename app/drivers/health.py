"""Device health monitoring types."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class HealthCheckResult:
    """Result of a single device health check."""

    device_id: str
    status: str  # "healthy" | "degraded" | "unhealthy"
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0


@dataclass(slots=True)
class DeviceHealth:
    """Aggregated health information for a device driver."""

    device_id: str
    status: str = "unknown"
    uptime_seconds: float = 0.0
    total_checks: int = 0
    consecutive_failures: int = 0
    last_check: HealthCheckResult | None = None
    error_rate: float = 0.0
    response_time_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "total_checks": self.total_checks,
            "consecutive_failures": self.consecutive_failures,
            "error_rate": self.error_rate,
            "response_time_ms": self.response_time_ms,
        }
