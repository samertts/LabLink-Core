from __future__ import annotations

import logging

from app.integration.gula_client import GulaClient
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ParserEngine
from app.storage.result_repository import LogRepository, ResultRepository

logger = logging.getLogger("lablink.pipeline")


class DataPipeline:
    def __init__(
        self,
        parser: ParserEngine,
        normalizer: Normalizer,
        result_repo: ResultRepository,
        log_repo: LogRepository,
        gula_client: GulaClient | None = None,
    ) -> None:
        self.parser = parser
        self.normalizer = normalizer
        self.result_repo = result_repo
        self.log_repo = log_repo
        self.gula_client = gula_client

    async def process_chunk(self, raw_data: str, *, patient_id: str, device_id: str) -> None:
        self.log_repo.add(device_id=device_id, raw_data=raw_data, status="received", error_message="")

        try:
            parsed_items = self.parser.feed(raw_data)
        except Exception as exc:
            self.log_repo.add(device_id=device_id, raw_data=raw_data, status="error", error_message=str(exc))
            logger.exception("Parser feed failed", extra={"device_id": device_id})
            return

        for parsed in parsed_items:
            try:
                normalized = self.normalizer.transform(parsed, patient_id=patient_id, device_id=device_id)
                self.result_repo.add(normalized)
                if self.gula_client:
                    await self.gula_client.send_results([normalized])
            except Exception as exc:
                self.log_repo.add(device_id=device_id, raw_data=raw_data, status="error", error_message=str(exc))
                logger.exception("Pipeline process failure", extra={"device_id": device_id})
