from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

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
    results: list[NormalizedResult]


class IngestService:
    """Orchestrates the data ingestion pipeline."""

    def __init__(
        self,
        pipeline: DataPipeline,
        repository: ResultRepository,
        sync_engine: SyncEngine,
        event_bus: EventBus | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._repository = repository
        self._sync_engine = sync_engine
        self._event_bus = event_bus
        self._metrics = metrics

    async def ingest(
        self,
        *,
        device_id: str,
        patient_id: str,
        chunk: str,
        vendor: str | None = None,
        barcode: str | None = None,
        current_mode: CommunicationMode = CommunicationMode.HYBRID,
    ) -> IngestResult:
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
        self._repository.save_results(results)

        if self._event_bus and results:
            self._event_bus.publish(
                ResultStored(device_id=device_id, count=len(results), source="ingest_service")
            )
        if self._metrics:
            self._metrics.increment("ingest.processed", tags={"device_id": device_id})
            self._metrics.histogram("ingest.batch_size", len(results))

        return IngestResult(status="ok", processed=len(results), results=results)

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
