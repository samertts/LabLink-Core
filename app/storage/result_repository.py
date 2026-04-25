from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from app.pipeline.normalizer import NormalizedResult
from app.storage.db import InMemoryDB


class ResultRepository:
    def __init__(self, db: InMemoryDB | None = None) -> None:
        self.db = db or InMemoryDB()
        self._legacy_items: list[NormalizedResult] = []

    def save_results(self, results: list[NormalizedResult]) -> None:
        for result in results:
            row = asdict(result)
            self.db.results.append(row)
            self._legacy_items.append(result)
            self.add_audit_event(
                event_type="result_saved",
                payload={
                    "device_id": result.device_id,
                    "patient_id": result.patient_id,
                    "test_code": result.test_code,
                },
            )

    def list_results(self) -> list[dict]:
        return list(self.db.results)

    # Backward-compatible alias used by early phase tests.
    def list(self) -> list[Any]:
        if self._legacy_items:
            return list(self._legacy_items)
        return [SimpleNamespace(**row) for row in self.list_results()]

    # Backward-compatible single-item insert used by early phase flows.
    def save(self, result: NormalizedResult) -> None:
        self.save_results([result])

    def save_log(self, *, device_id: str, raw_data: str, status: str, error_message: str = "") -> None:
        self.db.logs.append(
            {
                "device_id": device_id,
                "raw_data": raw_data,
                "status": status,
                "error_message": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def list_logs(self) -> list[dict]:
        return list(self.db.logs)

    def enqueue_offline(self, payload: dict[str, Any]) -> None:
        self.db.offline_queue.append(payload)
        self.add_audit_event(event_type="offline_enqueued", payload=payload)

    def list_offline_queue(self) -> list[dict]:
        return list(self.db.offline_queue)

    def add_audit_event(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self.db.audit_trail.append(
            {
                "event_type": event_type,
                "payload": payload,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def list_audit_trail(self) -> list[dict]:
        return list(self.db.audit_trail)


class LogRepository:
    """Backward-compatible repository facade for log persistence."""

    def __init__(self, db: InMemoryDB | None = None) -> None:
        self.db = db or InMemoryDB()

    def save(self, entry: dict[str, Any]) -> None:
        payload = {
            "device_id": entry.get("device_id", ""),
            "raw_data": entry.get("raw_data", ""),
            "status": entry.get("status", ""),
            "error_message": entry.get("error_message", ""),
            "timestamp": entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }
        self.db.logs.append(payload)

    def list(self) -> list[dict]:
        return list(self.db.logs)
