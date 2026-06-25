from __future__ import annotations

import logging
from typing import Any

from app.core.alerting import AlertManager
from app.storage.result_repository import ResultRepository

logger = logging.getLogger("lablink.services.query")


class QueryService:
    """Provides paginated read access to all persisted data."""

    def __init__(
        self,
        repository: ResultRepository,
        alerts: AlertManager,
    ) -> None:
        self._repository = repository
        self._alerts = alerts

    def list_results(self, limit: int = 100, offset: int = 0) -> list[dict]:
        return self._repository.list_results()[offset : offset + limit]

    def list_logs(self, limit: int = 100, offset: int = 0) -> list[dict]:
        return self._repository.list_logs()[offset : offset + limit]

    def list_audit_trail(self, limit: int = 100, offset: int = 0) -> list[dict]:
        return self._repository.list_audit_trail()[offset : offset + limit]

    def list_offline_queue(self, limit: int = 100, offset: int = 0) -> list[dict]:
        return self._repository.list_offline_queue()[offset : offset + limit]

    def list_alerts(self, limit: int = 100, offset: int = 0) -> list[dict[str, str]]:
        return self._alerts.list_alerts()[offset : offset + limit]

    def add_audit_event(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self._repository.add_audit_event(event_type=event_type, payload=payload)
