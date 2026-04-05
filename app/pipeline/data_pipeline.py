from __future__ import annotations

import logging

from app.integration.gula_client import GulaClient
from app.pipeline.normalizer import NormalizedResult, Normalizer
from app.pipeline.parser_engine import (
    ASTMBuffer,
    ASTMMessageBuilder,
    ASTMParser,
    ParsedResult,
    validate_checksum,
)

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
    ) -> None:
        self.parser = parser
        self.normalizer = normalizer
        self.gula_client = gula_client
        self.sessions: dict[str, ASTMDeviceSession] = {}

    async def process_chunk(
        self,
        *,
        device_id: str,
        fallback_patient_id: str,
        chunk: bytes,
    ) -> list[NormalizedResult]:
        session = self.sessions.setdefault(device_id, ASTMDeviceSession())
        session.buffer.append(chunk)

        normalized_results: list[NormalizedResult] = []
        for payload, received_checksum in session.buffer.extract_frames():
            try:
                validate_checksum(payload, received_checksum)
                records = self.parser.parse_frame(payload)
                message_rows = session.builder.process_records(records)

                for row in message_rows:
                    if not row["test_code"] or not row["value"]:
                        continue
                    parsed = ParsedResult(
                        test_code=row["test_code"],
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
            await self.gula_client.send_results(normalized_results)

        return normalized_results
