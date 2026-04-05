from __future__ import annotations

from dataclasses import dataclass

from app.normalization.schema import NormalizedResult


class ResultRepository:
    def __init__(self) -> None:
        self._items: list[NormalizedResult] = []

    def add(self, result: NormalizedResult) -> None:
        self._items.append(result)

    def list(self) -> list[NormalizedResult]:
        return list(self._items)


@dataclass(slots=True)
class LogEntry:
    device_id: str
    raw_data: str
    status: str
    error_message: str


class LogRepository:
    def __init__(self) -> None:
        self._items: list[LogEntry] = []

    def add(self, *, device_id: str, raw_data: str, status: str, error_message: str) -> None:
        self._items.append(
            LogEntry(
                device_id=device_id,
                raw_data=raw_data,
                status=status,
                error_message=error_message,
            )
        )

    def list(self) -> list[LogEntry]:
        return list(self._items)
