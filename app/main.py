from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.integration.gula_client import GulaClient
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import NormalizedResult, Normalizer
from app.pipeline.parser_engine import ASTMParser
from app.storage.db import InMemoryDB
from app.storage.result_repository import ResultRepository

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LabLink Core", version="0.3.0")

repository = ResultRepository(InMemoryDB())
pipeline = DataPipeline(
    parser=ASTMParser(),
    normalizer=Normalizer(),
    gula_client=GulaClient(base_url="http://gula.local", lab_id="LAB001"),
)


class IngestRequest(BaseModel):
    patient_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    chunk: str = Field(min_length=1, description="Raw ASTM chunk; may include control chars")


class IngestResponse(BaseModel):
    status: Literal["ok"]
    processed: int
    results: list[NormalizedResult]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest) -> IngestResponse:
    repository.save_log(device_id=payload.device_id, raw_data=payload.chunk, status="received")

    results = await pipeline.process_chunk(
        device_id=payload.device_id,
        fallback_patient_id=payload.patient_id,
        chunk=payload.chunk.encode("latin-1", errors="ignore"),
    )

    for _ in results:
        repository.save_log(
            device_id=payload.device_id,
            raw_data=payload.chunk,
            status="parsed",
            error_message="",
        )

    repository.save_results(results)
    return IngestResponse(status="ok", processed=len(results), results=results)


@app.get("/results")
def list_results() -> list[dict]:
    return repository.list_results()


@app.get("/logs")
def list_logs() -> list[dict]:
    return repository.list_logs()
