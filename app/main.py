from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.normalization.schema import NormalizedResult, normalize_result
from app.parsers.astm_basic import ASTMParseError, parse_astm_result_line

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lablink")

app = FastAPI(title="LabLink Core", version="0.1.0")

RESULTS_BUFFER: list[NormalizedResult] = []
RAW_LOGS: list[dict[str, str]] = []


class IngestRequest(BaseModel):
    lab_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    raw_data: str = Field(min_length=1, description="ASTM-like payload")


class IngestResponse(BaseModel):
    status: Literal["ok"]
    result: NormalizedResult


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest) -> IngestResponse:
    RAW_LOGS.append(
        {
            "device_id": payload.device_id,
            "raw_data": payload.raw_data,
            "status": "received",
            "error_message": "",
        }
    )

    try:
        parsed = parse_astm_result_line(payload.raw_data)
    except ASTMParseError as exc:
        RAW_LOGS.append(
            {
                "device_id": payload.device_id,
                "raw_data": payload.raw_data,
                "status": "error",
                "error_message": str(exc),
            }
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    normalized = normalize_result(
        parsed,
        patient_id=payload.patient_id,
        device_id=payload.device_id,
    )
    RESULTS_BUFFER.append(normalized)
    logger.info("Normalized result generated", extra={"test_code": normalized.test_code})

    return IngestResponse(status="ok", result=normalized)


@app.get("/results", response_model=list[NormalizedResult])
def list_results() -> list[NormalizedResult]:
    return RESULTS_BUFFER


@app.get("/logs")
def list_logs() -> list[dict[str, str]]:
    return RAW_LOGS
