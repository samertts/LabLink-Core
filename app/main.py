from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ParserEngine
from app.storage.result_repository import LogRepository, ResultRepository

app = FastAPI(title="LabLink Core", version="0.2.0")

RESULT_REPO = ResultRepository()
LOG_REPO = LogRepository()
PIPELINE = DataPipeline(
    parser=ParserEngine(),
    normalizer=Normalizer(),
    result_repo=RESULT_REPO,
    log_repo=LOG_REPO,
)


class IngestRequest(BaseModel):
    lab_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    raw_data: str = Field(min_length=1, description="ASTM-like payload chunk")


class IngestResponse(BaseModel):
    status: Literal["ok"]
    buffered_results: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest) -> IngestResponse:
    await PIPELINE.process_chunk(
        payload.raw_data,
        patient_id=payload.patient_id,
        device_id=payload.device_id,
    )
    return IngestResponse(status="ok", buffered_results=len(RESULT_REPO.list()))


@app.get("/results")
def list_results() -> list[dict[str, str | float]]:
    return [
        {
            "patient_id": item.patient_id,
            "device_id": item.device_id,
            "test_code": item.test_code,
            "test_name": item.test_name,
            "value": item.value,
            "unit": item.unit,
            "reference_range": item.reference_range,
            "timestamp": item.timestamp.isoformat(),
            "status": item.status,
        }
        for item in RESULT_REPO.list()
    ]


@app.get("/logs")
def list_logs() -> list[dict[str, str]]:
    return [
        {
            "device_id": item.device_id,
            "raw_data": item.raw_data,
            "status": item.status,
            "error_message": item.error_message,
        }
        for item in LOG_REPO.list()
    ]
