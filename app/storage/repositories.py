from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ResultRepositoryProtocol(ABC):
    """Interface for result persistence.

    Implementations may target SQLite, PostgreSQL, or in-memory stores.
    Business logic should depend only on this interface.
    """

    @abstractmethod
    def save_results(self, results: list[Any]) -> None: ...

    @abstractmethod
    def list_results(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def count_results(self) -> int: ...


class LogRepositoryProtocol(ABC):
    """Interface for log persistence."""

    @abstractmethod
    def save_log(self, *, device_id: str, raw_data: str, status: str, error_message: str = "") -> None: ...

    @abstractmethod
    def list_logs(self) -> list[dict[str, Any]]: ...


class AuditRepository(ABC):
    """Interface for audit trail persistence."""

    @abstractmethod
    def add_audit_event(self, *, event_type: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    def list_audit_trail(self) -> list[dict[str, Any]]: ...


class OfflineQueueRepository(ABC):
    """Interface for offline queue persistence."""

    @abstractmethod
    def enqueue_offline(self, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    def list_offline_queue(self) -> list[dict[str, Any]]: ...
