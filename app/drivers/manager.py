"""Driver manager: loads, manages, and coordinates device drivers."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.drivers.base import BaseDriver, ConnectionState
from app.drivers.diagnostics import DiagnosticReport, DriverDiagnostics
from app.drivers.errors import DriverError
from app.drivers.health import DeviceHealth, HealthCheckResult

logger = logging.getLogger(__name__)


class DriverManager:
    """Manages the lifecycle of all registered device drivers.

    Provides registration, connection management, health monitoring,
    diagnostics collection, and coordinated shutdown.
    """

    def __init__(self) -> None:
        self._drivers: dict[str, BaseDriver] = {}
        self._diagnostics = DriverDiagnostics()
        self._health_history: dict[str, list[HealthCheckResult]] = {}
        self._lock = threading.Lock()

    # ── Registration ────────────────────────────────────────────────

    def register(self, driver: BaseDriver) -> None:
        with self._lock:
            self._drivers[driver.device_id] = driver
            self._diagnostics.register(driver.device_id)
        logger.info(
            "Registered driver: %s (%s %s)",
            driver.device_id,
            driver.metadata.vendor,
            driver.metadata.model,
        )

    def unregister(self, device_id: str) -> BaseDriver | None:
        with self._lock:
            driver = self._drivers.pop(device_id, None)
            if driver:
                self._diagnostics.unregister(device_id)
                self._health_history.pop(device_id, None)
        return driver

    def get(self, device_id: str) -> BaseDriver | None:
        return self._drivers.get(device_id)

    def list_all(self) -> list[str]:
        return list(self._drivers.keys())

    def count(self) -> int:
        return len(self._drivers)

    # ── Connection management ───────────────────────────────────────

    def connect(self, device_id: str) -> None:
        driver = self._drivers.get(device_id)
        if driver is None:
            raise KeyError(f"Driver '{device_id}' not registered")
        try:
            driver._set_state(ConnectionState.CONNECTING)
            driver.connect()
            driver._set_state(ConnectionState.READY)
            logger.info("Connected driver: %s", device_id)
        except DriverError as exc:
            driver._record_error(str(exc))
            raise
        except Exception as exc:
            driver._record_error(f"Connection failed: {exc}")
            raise DriverError(str(exc), device_id=device_id) from exc

    def disconnect(self, device_id: str) -> None:
        driver = self._drivers.get(device_id)
        if driver is None:
            return
        try:
            driver.disconnect()
            driver._set_state(ConnectionState.DISCONNECTED)
            logger.info("Disconnected driver: %s", device_id)
        except Exception as exc:
            logger.error("Error disconnecting %s: %s", device_id, exc)

    def connect_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for device_id in list(self._drivers.keys()):
            try:
                self.connect(device_id)
                results[device_id] = True
            except Exception:
                results[device_id] = False
        return results

    def disconnect_all(self) -> None:
        for device_id in list(self._drivers.keys()):
            self.disconnect(device_id)

    # ── Health monitoring ───────────────────────────────────────────

    def health_check(self, device_id: str) -> HealthCheckResult:
        driver = self._drivers.get(device_id)
        if driver is None:
            return HealthCheckResult(
                device_id=device_id,
                status="unhealthy",
                message=f"Driver '{device_id}' not found",
            )

        import time

        start = time.monotonic()
        try:
            raw = driver.health_check()
            duration = (time.monotonic() - start) * 1000
            result = HealthCheckResult(
                device_id=device_id,
                status=raw.get("status", "healthy"),
                message=raw.get("message", ""),
                details={k: v for k, v in raw.items() if k not in ("status", "message")},
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            result = HealthCheckResult(
                device_id=device_id,
                status="unhealthy",
                message=str(exc),
                duration_ms=duration,
            )

        if device_id not in self._health_history:
            self._health_history[device_id] = []
        self._health_history[device_id].append(result)
        if len(self._health_history[device_id]) > 50:
            self._health_history[device_id] = self._health_history[device_id][-50:]

        return result

    def health_check_all(self) -> list[HealthCheckResult]:
        return [self.health_check(did) for did in list(self._drivers.keys())]

    def get_device_health(self, device_id: str) -> DeviceHealth:
        driver = self._drivers.get(device_id)
        if driver is None:
            return DeviceHealth(device_id=device_id, status="unknown")

        history = self._health_history.get(device_id, [])
        last = history[-1] if history else None
        failures = sum(1 for h in history if h.status == "unhealthy")
        total = len(history)

        return DeviceHealth(
            device_id=device_id,
            status=last.status if last else "unknown",
            total_checks=total,
            consecutive_failures=self._count_consecutive_failures(device_id),
            last_check=last,
            error_rate=failures / total if total > 0 else 0.0,
            response_time_ms=last.duration_ms if last else 0.0,
        )

    def _count_consecutive_failures(self, device_id: str) -> int:
        history = self._health_history.get(device_id, [])
        count = 0
        for h in reversed(history):
            if h.status == "unhealthy":
                count += 1
            else:
                break
        return count

    # ── Diagnostics ─────────────────────────────────────────────────

    def collect_diagnostics(self, device_id: str) -> DiagnosticReport | None:
        driver = self._drivers.get(device_id)
        if driver is None:
            return None
        return self._diagnostics.collect_from_driver(driver)

    def collect_all_diagnostics(self) -> dict[str, DiagnosticReport]:
        reports: dict[str, DiagnosticReport] = {}
        for device_id, driver in self._drivers.items():
            reports[device_id] = self._diagnostics.collect_from_driver(driver)
        return reports

    def get_diagnostics_summary(self) -> dict[str, Any]:
        return self._diagnostics.get_summary()

    # ── Data exchange ───────────────────────────────────────────────

    def read_data(self, device_id: str) -> bytes:
        driver = self._drivers.get(device_id)
        if driver is None:
            raise KeyError(f"Driver '{device_id}' not found")
        return driver.read_data()

    def write_data(self, device_id: str, data: bytes) -> None:
        driver = self._drivers.get(device_id)
        if driver is None:
            raise KeyError(f"Driver '{device_id}' not found")
        driver.write_data(data)

    def send_command(self, device_id: str, command: str) -> str:
        driver = self._drivers.get(device_id)
        if driver is None:
            raise KeyError(f"Driver '{device_id}' not found")
        return driver.send_command(command)

    # ── Summary ─────────────────────────────────────────────────────

    def summary(self) -> list[dict[str, Any]]:
        result = []
        for did, driver in self._drivers.items():
            health = self.get_device_health(did)
            result.append({
                "device_id": did,
                "vendor": driver.metadata.vendor,
                "model": driver.metadata.model,
                "state": driver.state.value,
                "health_status": health.status,
                "error_count": driver.error_count,
                "capabilities": {
                    "realtime": driver.capabilities().supports_realtime,
                    "protocols": list(driver.capabilities().supported_protocols),
                },
            })
        return result

    # ── Shutdown ────────────────────────────────────────────────────

    def shutdown(self) -> None:
        logger.info("Shutting down driver manager (%d drivers)", len(self._drivers))
        self.disconnect_all()
        logger.info("Driver manager shut down")
