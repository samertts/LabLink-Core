from __future__ import annotations

import logging
from typing import Any

from app.adapters.registry import AdapterRegistry
from app.core.retry_queue import RetryQueue
from app.edge.agent import EdgeAgentBuffer
from app.integration.gula_client import GulaClient
from app.pipeline.normalizer import NormalizedResult, Normalizer
from app.pipeline.parser_engine import (
    ASTMBuffer,
    ASTMMessageBuilder,
    ASTMParser,
    ParsedResult,
    validate_checksum,
)
from app.pipeline.patient_matching import PatientMatcher
from app.pipeline.smart_router import SmartRoutingEngine
from app.pipeline.test_mapping import TestMappingEngine
from app.storage.result_repository import LogRepository, ResultRepository

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
        gula_client: GulaClient | None = None,
        result_repo: ResultRepository | None = None,
        log_repo: LogRepository | None = None,
        mapping_engine: TestMappingEngine | None = None,
        retry_queue: RetryQueue | None = None,
        adapter_registry: AdapterRegistry | None = None,
        patient_matcher: PatientMatcher | None = None,
        router: SmartRoutingEngine | None = None,
        edge_buffer: EdgeAgentBuffer | None = None,
    ) -> None:
        self.parser = parser
        self.normalizer = normalizer
        self.gula_client = gula_client or GulaClient(base_url="http://localhost:8000", lab_id="LABLINK")
        self.result_repo = result_repo
        self.log_repo = log_repo
        self.mapping_engine = mapping_engine or TestMappingEngine()
        self.retry_queue = retry_queue or RetryQueue()
        self.adapter_registry = adapter_registry or AdapterRegistry()
        self.patient_matcher = patient_matcher or PatientMatcher()
        self.router = router or SmartRoutingEngine()
        self.edge_buffer = edge_buffer or EdgeAgentBuffer()
        self.sessions: dict[str, ASTMDeviceSession] = {}

    async def process_chunk(self, *args: Any, **kwargs: Any) -> list[NormalizedResult]:
        # Backward-compatible path for legacy tests.
        if args and isinstance(args[0], str):
            raw_chunk = args[0]
            patient_id = kwargs["patient_id"]
            device_id = kwargs["device_id"]

            parsed_rows = self.parser.feed(raw_chunk)  # type: ignore[attr-defined]
            normalized_results = [
                self.normalizer.transform(row, patient_id=patient_id, device_id=device_id) for row in parsed_rows
            ]

            if self.result_repo is not None:
                self.result_repo.save_results(normalized_results)
            if self.log_repo is not None:
                self.log_repo.save(device_id=device_id, raw_data=raw_chunk, status="parsed")

            return normalized_results

        device_id = kwargs["device_id"]
        fallback_patient_id = kwargs["fallback_patient_id"]
        chunk = kwargs["chunk"]
        vendor = kwargs.get("vendor")
        barcode = kwargs.get("barcode")

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
                    patient_id = self.patient_matcher.resolve_patient_id(
                        row_patient_id=row["patient_id"],
                        fallback_patient_id=fallback_patient_id,
                        barcode=barcode,
                    )
                    parsed = ParsedResult(
                        test_code=canonical,
                        value=float(row["value"]),
                        unit=row["unit"],
                    )
                    normalized = self.normalizer.transform(
                        parsed,
                        patient_id=patient_id,
                        device_id=device_id,
                    )
                    normalized_results.append(normalized)
            except Exception:
                logger.exception("Invalid ASTM frame", extra={"device_id": device_id})

        if not normalized_results:
            return normalized_results

        decision = self.router.decide(device_id=device_id, results=normalized_results)

        if decision.target in {"gula", "both"}:
            response = await self.gula_client.send_results(normalized_results)
            if response.get("status") == "failed":
                self.retry_queue.enqueue(
                    {
                        "device_id": device_id,
                        "results": [r.test_code for r in normalized_results],
                        "reason": response.get("error", "send_failed"),
                    }
                )
                self.edge_buffer.enqueue(
                    {
                        "device_id": device_id,
                        "results": [r.test_code for r in normalized_results],
                    }
                )

        if decision.target in {"offline", "both"}:
            self.edge_buffer.enqueue(
                {
                    "device_id": device_id,
                    "results": [r.test_code for r in normalized_results],
                }
            )

        return normalized_results
