from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any


class AlertManager:
    """Thread-safe alert manager with bounded storage."""

    MAX_ALERTS = 1000

    def __init__(self, max_alerts: int = MAX_ALERTS) -> None:
        self._alerts: list[dict[str, str]] = []
        self._lock = threading.Lock()
        self._max_alerts = max_alerts

    def emit(self, *, severity: str, message: str, device_id: str) -> None:
        with self._lock:
            self._alerts.append(
                {
                    "severity": severity,
                    "message": message,
                    "device_id": device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            if len(self._alerts) > self._max_alerts:
                self._alerts = self._alerts[-self._max_alerts:]

    def list_alerts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._alerts)

    def clear(self) -> None:
        with self._lock:
            self._alerts.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._alerts)
