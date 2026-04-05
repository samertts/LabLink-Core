from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from app.pipeline.normalizer import NormalizedResult
from app.storage.db import InMemoryDB


class ResultRepository:
    def __init__(self, db: InMemoryDB) -> None:
        self.db = db

    def save_results(self, results: list[NormalizedResult]) -> None:
        for result in results:
            row = asdict(result)
            self.db.results.append(row)
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
