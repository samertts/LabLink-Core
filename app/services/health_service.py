from __future__ import annotations

import logging
from dataclasses import dataclass

from app.storage.db import InMemoryDB

logger = logging.getLogger("lablink.services.health")

VERSION = "1.2.0"


@dataclass(frozen=True)
class HealthStatus:
    status: str
    version: str
    checks: dict[str, str]


class HealthService:
    """Provides health check and readiness probe logic."""

    def __init__(self, db: InMemoryDB) -> None:
        self._db = db

    def check(self) -> HealthStatus:
        checks: dict[str, str] = {}
        try:
            self._db.integrity_check()
            checks["database"] = "ok"
        except Exception:
            logger.exception("Database integrity check failed")
            checks["database"] = "error"
        return HealthStatus(status="ok", version=VERSION, checks=checks)
