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
    ParserEngine,
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
        parser: ASTMParser | ParserEngine,
        normalizer: Normalizer,
        gula_client: GulaClient | None = None,
        mapping_engine: TestMappingEngine | None = None,
        retry_queue: RetryQueue | None = None,
        adapter_registry: AdapterRegistry | None = None,
        patient_matcher: PatientMatcher | None = None,
        router: SmartRoutingEngine | None = None,
        edge_buffer: EdgeAgentBuffer | None = None,
        result_repo: ResultRepository | None = None,
        log_repo: LogRepository | None = None,
    ) -> None:
        self.parser = parser
        self.normalizer = normalizer
        self.gula_client = gula_client or GulaClient(base_url="http://gula.local", lab_id="LAB001")
        self.mapping_engine = mapping_engine or TestMappingEngine()
        self.retry_queue = retry_queue or RetryQueue()
        self.adapter_registry = adapter_registry or AdapterRegistry()
        self.patient_matcher = patient_matcher or PatientMatcher()
        self.router = router or SmartRoutingEngine()
        self.edge_buffer = edge_buffer or EdgeAgentBuffer()
        self.result_repo = result_repo or ResultRepository()
        self.log_repo = log_repo or LogRepository()
        self.sessions: dict[str, ASTMDeviceSession] = {}

    async def process_chunk(
        self,
        chunk: bytes | str,
        device_id: str,
        fallback_patient_id: str | None = None,
        patient_id: str | None = None,
        vendor: str | None = None,
        barcode: str | None = None,
    ) -> list[NormalizedResult]:
        if isinstance(chunk, str):
            return self._process_legacy_chunk(chunk=chunk, patient_id=patient_id, device_id=device_id)

        resolved_patient_id = fallback_patient_id or patient_id or "UNKNOWN"
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
                        fallback_patient_id=resolved_patient_id,
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

        self.result_repo.save_results(normalized_results)
        self.log_repo.save(
            {
                "device_id": device_id,
                "raw_data": chunk.decode("ascii", errors="ignore"),
                "status": "processed",
            }
        )

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

    def _process_legacy_chunk(self, *, chunk: str, patient_id: str | None, device_id: str) -> list[NormalizedResult]:
        if not isinstance(self.parser, ParserEngine):
            raise TypeError("Legacy string chunk flow requires ParserEngine")

        normalized_results: list[NormalizedResult] = []
        for parsed in self.parser.feed(chunk):
            normalized = self.normalizer.transform(
                parsed,
                patient_id=patient_id or "UNKNOWN",
                device_id=device_id,
            )
            normalized_results.append(normalized)

        if normalized_results:
            self.result_repo.save_results(normalized_results)
            self.log_repo.save(
                {
                    "device_id": device_id,
                    "raw_data": chunk,
                    "status": "processed",
                }
            )

        return normalized_results
