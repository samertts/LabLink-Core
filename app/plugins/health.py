"""Plugin health checking subsystem."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.plugins.base import PluginState
from app.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HealthCheckResult:
    """Result of a single plugin health check."""

    plugin_name: str
    status: str  # "healthy" | "degraded" | "unhealthy"
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0


class PluginHealthChecker:
    """Runs health checks against all activated plugins.

    Maintains a history of recent results for diagnostics and
    exposes aggregate health status for the platform health endpoint.
    """

    MAX_HISTORY = 100

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry
        self._history: dict[str, list[HealthCheckResult]] = {}

    def check_plugin(self, name: str) -> HealthCheckResult:
        plugin = self._registry.get(name)
        if plugin is None:
            return HealthCheckResult(
                plugin_name=name,
                status="unhealthy",
                message=f"Plugin '{name}' not found",
            )

        state = self._registry.get_state(name)
        if state != PluginState.ACTIVATED:
            return HealthCheckResult(
                plugin_name=name,
                status="degraded",
                message=f"Plugin state is {state.value}, not activated",
            )

        start = time.monotonic()
        try:
            raw = plugin.health_check()
            duration = (time.monotonic() - start) * 1000
            status = raw.get("status", "healthy")
            result = HealthCheckResult(
                plugin_name=name,
                status=status,
                message=raw.get("message", ""),
                details={k: v for k, v in raw.items() if k not in ("status", "message")},
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            result = HealthCheckResult(
                plugin_name=name,
                status="unhealthy",
                message=str(exc),
                duration_ms=duration,
            )

        self._record_result(name, result)
        return result

    def check_all(self) -> list[HealthCheckResult]:
        activated = self._registry.list_by_state(PluginState.ACTIVATED)
        return [self.check_plugin(name) for name in activated]

    def get_overall_status(self) -> str:
        results = self.check_all()
        if not results:
            return "healthy"
        statuses = {r.status for r in results}
        if "unhealthy" in statuses:
            return "unhealthy"
        if "degraded" in statuses:
            return "degraded"
        return "healthy"

    def get_last_result(self, name: str) -> HealthCheckResult | None:
        history = self._history.get(name, [])
        return history[-1] if history else None

    def get_history(self, name: str, limit: int = 10) -> list[HealthCheckResult]:
        return list(reversed(self._history.get(name, [])[-limit:]))

    def _record_result(self, name: str, result: HealthCheckResult) -> None:
        if name not in self._history:
            self._history[name] = []
        self._history[name].append(result)
        if len(self._history[name]) > self.MAX_HISTORY:
            self._history[name] = self._history[name][-self.MAX_HISTORY :]
