from __future__ import annotations

import logging
from dataclasses import dataclass

from app.events.base import EventBus
from app.events.domain import HealthChanged
from app.observability.metrics import MetricsCollector
from app.storage.db import InMemoryDB

logger = logging.getLogger("lablink.services.health")

VERSION = "1.3.0"


@dataclass(frozen=True)
class HealthStatus:
    status: str
    version: str
    checks: dict[str, str]


class HealthService:
    """Provides health check and readiness probe logic."""

    def __init__(
        self,
        db: InMemoryDB,
        event_bus: EventBus | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._db = db
        self._event_bus = event_bus
        self._metrics = metrics

    def check(self) -> HealthStatus:
        checks: dict[str, str] = {}
        try:
            self._db.integrity_check()
            checks["database"] = "ok"
        except Exception:
            logger.exception("Database integrity check failed")
            checks["database"] = "error"

        if self._metrics:
            db_ok = 1.0 if checks.get("database") == "ok" else 0.0
            self._metrics.gauge("health.database", db_ok)

        if self._event_bus:
            self._event_bus.publish(
                HealthChanged(
                    status="ok" if checks.get("database") == "ok" else "degraded",
                    checks=checks,
                    source="health_service",
                )
            )

        return HealthStatus(status="ok", version=VERSION, checks=checks)
