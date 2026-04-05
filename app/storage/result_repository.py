from __future__ import annotations

from dataclasses import asdict

from app.pipeline.normalizer import NormalizedResult
from app.storage.db import InMemoryDB


class ResultRepository:
    def __init__(self, db: InMemoryDB) -> None:
        self.db = db

    def save_results(self, results: list[NormalizedResult]) -> None:
        for result in results:
            self.db.results.append(asdict(result))

    def list_results(self) -> list[dict]:
        return list(self.db.results)

    def save_log(self, *, device_id: str, raw_data: str, status: str, error_message: str = "") -> None:
        self.db.logs.append(
            {
                "device_id": device_id,
                "raw_data": raw_data,
                "status": status,
                "error_message": error_message,
            }
        )

    def list_logs(self) -> list[dict]:
        return list(self.db.logs)
