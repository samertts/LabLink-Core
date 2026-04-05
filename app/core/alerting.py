from __future__ import annotations

from datetime import datetime, timezone


class AlertManager:
    def __init__(self) -> None:
        self._alerts: list[dict[str, str]] = []

    def emit(self, *, severity: str, message: str, device_id: str) -> None:
        self._alerts.append(
            {
                "severity": severity,
                "message": message,
                "device_id": device_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def list_alerts(self) -> list[dict[str, str]]:
        return list(self._alerts)
