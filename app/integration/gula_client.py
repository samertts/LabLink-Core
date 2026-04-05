from __future__ import annotations

from typing import Any

import httpx

from app.normalization.schema import NormalizedResult


class GulaClient:
    def __init__(self, base_url: str, lab_id: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.lab_id = lab_id
        self.timeout = timeout

    async def send_results(self, results: list[NormalizedResult]) -> dict[str, Any]:
        payload = {
            "lab_id": self.lab_id,
            "results": [
                {
                    "patient_id": r.patient_id,
                    "test_code": r.test_code,
                    "value": r.value,
                    "unit": r.unit,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in results
            ],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/v1/results", json=payload)
            response.raise_for_status()
            return response.json()
