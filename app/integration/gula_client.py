from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from app.contracts.device_observation import PendingDeviceObservation
from app.pipeline.normalizer import NormalizedResult

logger = logging.getLogger("lablink.gula")


class GulaClient:
    def __init__(
        self,
        base_url: str,
        lab_id: str,
        timeout: float = 5.0,
        max_retries: int = 3,
        access_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.lab_id = lab_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.access_token = access_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    async def _post_with_retry(self, envelope: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post(
                    f"{self.base_url}/integrations/events",
                    json=envelope,
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))
        logger.error("GULA event delivery failed after %d attempts", self.max_retries)
        return {"status": "failed", "error": str(last_error) if last_error else "unknown_error"}

    async def send_pending_observations(
        self, observations: Iterable[PendingDeviceObservation]
    ) -> list[dict[str, Any]]:
        """Publish observations as pending events; never marks them approved."""
        responses: list[dict[str, Any]] = []
        for observation in observations:
            event_id = "evt-" + hashlib.sha256(observation.idempotency_key.encode()).hexdigest()[:32]
            envelope = {
                "event_id": event_id,
                "event_type": "device.observation.pending",
                "schema_version": 1,
                "source_service": "lablink-core",
                "tenant_id": self.lab_id,
                "occurred_at": observation.observed_at.astimezone(timezone.utc).isoformat(),
                "actor_id": observation.device_id,
                "entity_id": observation.sample_id,
                "correlation_id": str(uuid.uuid4()),
                "idempotency_key": observation.idempotency_key,
                "payload": {
                    "sample_id": observation.sample_id,
                    "observation_id": observation.observation_id,
                    "patient_id": observation.patient_id,
                    "device_id": observation.device_id,
                    "test_code": observation.test_code,
                    "value": observation.value,
                    "unit": observation.unit,
                    "reference_range": observation.reference_range,
                    "status": "pending_review",
                    "provenance": observation.provenance,
                },
            }
            responses.append(await self._post_with_retry(envelope))
        return responses

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
