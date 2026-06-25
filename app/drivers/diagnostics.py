"""Driver diagnostics collection and reporting."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DiagnosticReport:
    """A point-in-time diagnostic snapshot for a driver."""

    device_id: str
    timestamp: float = field(default_factory=time.time)
    driver_info: dict[str, Any] = field(default_factory=dict)
    connection_info: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "driver_info": self.driver_info,
            "connection_info": self.connection_info,
            "performance": self.performance,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": {
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
                "healthy": len(self.errors) == 0,
            },
        }


class DriverDiagnostics:
    """Collects and aggregates diagnostics across multiple drivers.

    Maintains a history of diagnostic reports and provides summary
    views for the platform health endpoint.
    """

    MAX_REPORTS_PER_DEVICE = 50

    def __init__(self) -> None:
        self._reports: dict[str, list[DiagnosticReport]] = {}
        self._start_times: dict[str, float] = {}

    def register(self, device_id: str) -> None:
        self._start_times[device_id] = time.time()

    def unregister(self, device_id: str) -> None:
        self._start_times.pop(device_id, None)
        self._reports.pop(device_id, None)

    def record(self, report: DiagnosticReport) -> None:
        if report.device_id not in self._reports:
            self._reports[report.device_id] = []
        self._reports[report.device_id].append(report)
        if len(self._reports[report.device_id]) > self.MAX_REPORTS_PER_DEVICE:
            self._reports[report.device_id] = self._reports[report.device_id][-self.MAX_REPORTS_PER_DEVICE:]

    def get_latest(self, device_id: str) -> DiagnosticReport | None:
        reports = self._reports.get(device_id, [])
        return reports[-1] if reports else None

    def get_history(self, device_id: str, limit: int = 10) -> list[DiagnosticReport]:
        return list(reversed(self._reports.get(device_id, [])[-limit:]))

    def get_all_device_ids(self) -> list[str]:
        ids = set(self._reports.keys())
        ids.update(self._start_times.keys())
        return sorted(ids)

    def get_summary(self) -> dict[str, Any]:
        total_errors = 0
        total_warnings = 0
        for reports in self._reports.values():
            if reports:
                latest = reports[-1]
                total_errors += len(latest.errors)
                total_warnings += len(latest.warnings)
        return {
            "device_count": len(self._reports),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "devices": {
                did: {
                    "report_count": len(reps),
                    "latest_status": "healthy" if reps and not reps[-1].errors else "unhealthy",
                }
                for did, reps in self._reports.items()
            },
        }

    def collect_from_driver(self, driver: Any) -> DiagnosticReport:
        """Create a DiagnosticReport from a driver's collect_diagnostics()."""
        data = driver.collect_diagnostics() if hasattr(driver, "collect_diagnostics") else {}
        return DiagnosticReport(
            device_id=getattr(driver, "device_id", "unknown"),
            driver_info=data,
            connection_info={"state": data.get("state", "unknown")},
        )
