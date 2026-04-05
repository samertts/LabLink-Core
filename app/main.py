from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core.device_manager import DeviceManager
from app.integration.gula_client import GulaClient
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import NormalizedResult, Normalizer
from app.pipeline.parser_engine import ASTMParser
from app.storage.db import InMemoryDB
from app.storage.result_repository import ResultRepository

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LabLink Core", version="0.4.0")

repository = ResultRepository(InMemoryDB())
device_manager = DeviceManager()
pipeline = DataPipeline(
    parser=ASTMParser(),
    normalizer=Normalizer(),
    gula_client=GulaClient(base_url="http://gula.local", lab_id="LAB001"),
)


class IngestRequest(BaseModel):
    patient_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    chunk: str = Field(min_length=1, description="Raw ASTM chunk; may include control chars")
    vendor: str | None = None


class IngestResponse(BaseModel):
    status: Literal["ok"]
    processed: int
    results: list[NormalizedResult]


class RegisterDeviceRequest(BaseModel):
    device_id: str
    type: Literal["tcp", "serial"]
    host: str | None = None
    port: int | None = None
    path: str | None = None
    baudrate: int = 9600
    vendor: str = "unknown"
    device_type: str = "unknown"
    protocol: str = "ASTM"


class CommandRequest(BaseModel):
    command: str = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/devices/register")
def register_device(payload: RegisterDeviceRequest) -> dict[str, str]:
    config = payload.model_dump(exclude_none=True)
    try:
        device_manager.add_device(config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "registered", "device_id": payload.device_id}


@app.get("/devices")
def list_devices() -> list[dict]:
    return [
        {
            "device_id": d.device_id,
            "is_connected": d.is_connected,
        }
        for d in device_manager.list_devices()
    ]


@app.get("/registry")
def list_registry() -> list[dict]:
    return [
        {
            "device_id": item.device_id,
            "device_type": item.device_type,
            "vendor": item.vendor,
            "protocol": item.protocol,
            "connection": item.connection,
        }
        for item in device_manager.list_registry()
    ]


@app.post("/devices/{device_id}/command")
def send_device_command(device_id: str, payload: CommandRequest) -> dict[str, str]:
    try:
        device_manager.send_command(device_id, payload.command)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "sent", "device_id": device_id}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest) -> IngestResponse:
    repository.save_log(device_id=payload.device_id, raw_data=payload.chunk, status="received")

    results = await pipeline.process_chunk(
        device_id=payload.device_id,
        fallback_patient_id=payload.patient_id,
        chunk=payload.chunk.encode("latin-1", errors="ignore"),
        vendor=payload.vendor,
    )

    if pipeline.retry_queue.size() > 0:
        for item in pipeline.retry_queue.list_all():
            repository.enqueue_offline(item)

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


@app.get("/audit")
def list_audit() -> list[dict]:
    return repository.list_audit_trail()


@app.get("/offline-queue")
def list_offline_queue() -> list[dict]:
    return repository.list_offline_queue()
