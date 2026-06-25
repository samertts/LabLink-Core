from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.pipeline.normalizer import NormalizedResult

logger = logging.getLogger("lablink.gula")


class GulaClient:
    def __init__(self, base_url: str, lab_id: str, timeout: float = 5.0, max_retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.lab_id = lab_id
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

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

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post(f"{self.base_url}/api/v1/results", json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait = 2 ** (attempt - 1)
                    logger.warning(
                        "GULA send failed (attempt %d/%d); retrying in %ds",
                        attempt,
                        self.max_retries,
                        wait,
                        extra={"lab_id": self.lab_id, "error": str(exc)},
                    )
                    await asyncio.sleep(wait)

        logger.error("GULA send failed after %d attempts", self.max_retries, extra={"lab_id": self.lab_id})
        return {"status": "failed", "error": str(last_error) if last_error else "unknown_error"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
