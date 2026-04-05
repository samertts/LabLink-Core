from __future__ import annotations

import logging

from app.adapters.registry import AdapterRegistry
from app.core.retry_queue import RetryQueue
from app.integration.gula_client import GulaClient
from app.pipeline.normalizer import NormalizedResult, Normalizer
from app.pipeline.parser_engine import (
    ASTMBuffer,
    ASTMMessageBuilder,
    ASTMParser,
    ParsedResult,
    validate_checksum,
)
from app.pipeline.test_mapping import TestMappingEngine

logger = logging.getLogger("lablink.pipeline")


class ASTMDeviceSession:
    def __init__(self) -> None:
        self.buffer = ASTMBuffer()
        self.builder = ASTMMessageBuilder()


class DataPipeline:
    def __init__(
        self,
        *,
        parser: ASTMParser,
        normalizer: Normalizer,
        gula_client: GulaClient,
        mapping_engine: TestMappingEngine | None = None,
        retry_queue: RetryQueue | None = None,
        adapter_registry: AdapterRegistry | None = None,
    ) -> None:
        self.parser = parser
        self.normalizer = normalizer
        self.gula_client = gula_client
        self.mapping_engine = mapping_engine or TestMappingEngine()
        self.retry_queue = retry_queue or RetryQueue()
        self.adapter_registry = adapter_registry or AdapterRegistry()
        self.sessions: dict[str, ASTMDeviceSession] = {}

    async def process_chunk(
        self,
        *,
        device_id: str,
        fallback_patient_id: str,
        chunk: bytes,
        vendor: str | None = None,
    ) -> list[NormalizedResult]:
        session = self.sessions.setdefault(device_id, ASTMDeviceSession())
        session.buffer.append(chunk)
        adapter = self.adapter_registry.resolve(vendor)

        normalized_results: list[NormalizedResult] = []
        for payload, received_checksum in session.buffer.extract_frames():
            try:
                validate_checksum(payload, received_checksum)
                records = self.parser.parse_frame(payload)
                message_rows = session.builder.process_records(records)
                message_rows = adapter.transform_rows(message_rows)

                for row in message_rows:
                    if not row["test_code"] or not row["value"]:
                        continue
                    canonical = self.mapping_engine.canonical_code(row["test_code"])
                    parsed = ParsedResult(
                        test_code=canonical,
                        value=float(row["value"]),
                        unit=row["unit"],
                    )
                    normalized = self.normalizer.transform(
                        parsed,
                        patient_id=row["patient_id"] or fallback_patient_id,
                        device_id=device_id,
                    )
                    normalized_results.append(normalized)
            except Exception:
                logger.exception("Invalid ASTM frame", extra={"device_id": device_id})

        if normalized_results:
            response = await self.gula_client.send_results(normalized_results)
            if response.get("status") == "failed":
                self.retry_queue.enqueue(
                    {
                        "device_id": device_id,
                        "results": [r.test_code for r in normalized_results],
                        "reason": response.get("error", "send_failed"),
                    }
                )

        return normalized_results
