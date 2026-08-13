from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from hashlib import sha256

from app.contracts.device_observation import PendingDeviceObservation, build_pending_observation

from app.core.modes import CommunicationMode
from app.edge.sync_engine import SyncEngine
from app.events.base import EventBus
from app.events.domain import ResultNormalized, ResultReceived, ResultStored, SyncCompleted, SyncStarted
from app.observability.metrics import MetricsCollector
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import NormalizedResult
from app.storage.result_repository import ResultRepository

logger = logging.getLogger("lablink.services.ingest")


@dataclass(frozen=True)
class IngestResult:
    status: str
    processed: int
    results: list[PendingDeviceObservation]


class IngestService:
    """Orchestrates the data ingestion pipeline."""

    def __init__(
        self,
        pipeline: DataPipeline,
        repository: ResultRepository,
        sync_engine: SyncEngine,
        event_bus: EventBus | None = None,
        metrics: MetricsCollector | None = None,
        gula_client=None,
    ) -> None:
        self._pipeline = pipeline
        self._repository = repository
        self._sync_engine = sync_engine
        self._event_bus = event_bus
        self._metrics = metrics
        self._gula_client = gula_client

    async def ingest(
        self,
        *,
        device_id: str,
        patient_id: str,
        chunk: str,
        vendor: str | None = None,
        barcode: str | None = None,
        sample_id: str | None = None,
        current_mode: CommunicationMode = CommunicationMode.HYBRID,
    ) -> IngestResult:
        resolved_sample_id = (sample_id or barcode or "").strip()
        if not resolved_sample_id:
            raise ValueError("sample_id or barcode is required for device observations")
        self._repository.save_log(device_id=device_id, raw_data=chunk, status="received")

        if self._event_bus:
            self._event_bus.publish(
                ResultReceived(device_id=device_id, patient_id=patient_id, chunk_length=len(chunk), source="ingest_service")
            )
        if self._metrics:
            self._metrics.increment("ingest.received", tags={"device_id": device_id})

        if current_mode == CommunicationMode.LOCAL_ONLY:
            self._pipeline.router.set_policy(device_id, "offline")
        elif current_mode == CommunicationMode.CLOUD_ONLY:
            self._pipeline.router.set_policy(device_id, "gula")

        results = await self._pipeline.process_chunk(
            device_id=device_id,
            fallback_patient_id=patient_id,
            chunk=chunk.encode("latin-1", errors="ignore"),
            vendor=vendor,
            barcode=barcode,
        )

        if self._event_bus and results:
            for result in results:
                self._event_bus.publish(
                    ResultNormalized(
                        device_id=device_id,
                        test_code=result.test_code,
                        value=result.value,
                        source="ingest_service",
                    )
                )

        self._drain_retry_queue()
        pending_results = [replace(result, status="pending_review") for result in results]
        self._repository.save_results(pending_results)
        provenance_digest = sha256(chunk.encode("latin-1", errors="ignore")).hexdigest()[:16]
        observations = [
            build_pending_observation(
                result,
                sample_id=resolved_sample_id,
                provenance=f"{vendor or 'unknown'}:{device_id}:{provenance_digest}",
            )
            for result in results
        ]

        if self._gula_client and observations:
            try:
                await self._gula_client.send_pending_observations(observations)
            except Exception:
                logger.exception("Failed to publish pending observations to GULA")

        if self._event_bus and results:
            self._event_bus.publish(
                ResultStored(device_id=device_id, count=len(results), source="ingest_service")
            )
        if self._metrics:
            self._metrics.increment("ingest.processed", tags={"device_id": device_id})
            self._metrics.histogram("ingest.batch_size", len(results))

        return IngestResult(status="ok", processed=len(observations), results=observations)

    def _drain_retry_queue(self) -> None:
        while self._pipeline.retry_queue.size() > 0:
            item = self._pipeline.retry_queue.dequeue()
            if item is None:
                break
            self._repository.enqueue_offline(item)
            self._sync_engine.stage(
                item_id=str(uuid.uuid4()),
                device_id=item["device_id"],
                payload=item,
                version=1,
            )

    async def sync_edge_buffer(self) -> dict[str, int]:
        if self._event_bus:
            self._event_bus.publish(SyncStarted(source="ingest_service"))

        async def sender(payload: dict) -> dict:
            self._pipeline.edge_buffer.enqueue(payload)
            return {"status": "ok"}

        result = await self._sync_engine.sync(sender)

        if self._event_bus:
            self._event_bus.publish(
                SyncCompleted(sent=result.get("sent", 0), failed=result.get("failed", 0), source="ingest_service")
            )
        if self._metrics:
            self._metrics.increment("sync.completed")
            self._metrics.gauge("sync.items_sent", result.get("sent", 0))

        return result

    def set_device_routing(self, device_id: str, policy: str) -> dict[str, str]:
        self._pipeline.router.set_policy(device_id, policy)
        return {"status": "updated", "device_id": device_id, "policy": policy}
