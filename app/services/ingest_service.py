from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.core.modes import CommunicationMode
from app.edge.sync_engine import SyncEngine
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
    ) -> None:
        self._pipeline = pipeline
        self._repository = repository
        self._sync_engine = sync_engine

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

        self._drain_retry_queue()
        self._repository.save_results(results)

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
        async def sender(payload: dict) -> dict:
            self._pipeline.edge_buffer.enqueue(payload)
            return {"status": "ok"}

        return await self._sync_engine.sync(sender)

    def set_device_routing(self, device_id: str, policy: str) -> dict[str, str]:
        self._pipeline.router.set_policy(device_id, policy)
        return {"status": "updated", "device_id": device_id, "policy": policy}
