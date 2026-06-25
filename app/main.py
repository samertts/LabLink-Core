from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.core.modes import CommunicationMode
from app.middleware.rate_limit import RateLimitMiddleware
from app.pipeline.normalizer import NormalizedResult
from app.security.auth import verify_api_key
from app.services.service_container import ServiceContainer, create_service_container

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lablink.api")

_container: ServiceContainer | None = None


def _get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = create_service_container()
    return _container


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _container
    settings = get_settings()
    _container = create_service_container(settings)
    if settings.worker_enabled:
        _container.worker.start()
    logger.info("LabLink Core started (v1.3.0)")
    yield
    logger.info("Shutting down LabLink Core...")
    _container.worker.stop()
    _container.device_service.shutdown()
    await _container.pipeline.gula_client.close()
    _container.db.close()
    logger.info("Shutdown complete.")


app = FastAPI(title="LabLink Core", version="1.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)

Auth = Annotated[str, Depends(verify_api_key)]


class IngestRequest(BaseModel):
    patient_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    chunk: str = Field(min_length=1, description="Raw ASTM chunk; may include control chars")
    vendor: str | None = None
    barcode: str | None = None


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
    command: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_\-\. \|]+$")


class RoutingPolicyRequest(BaseModel):
    policy: Literal["gula", "offline", "both"]


class ModeRequest(BaseModel):
    mode: CommunicationMode


class DeviceScanRequest(BaseModel):
    os_name: Literal["windows", "linux", "macos"]
    supports_wireless: bool = True
    required_mbps: int = Field(default=50, ge=1, le=10_000)
    max_latency_ms: int = Field(default=20, ge=1, le=1_000)
    distance_meters: int = Field(default=10, ge=1, le=200)
    deployment_target: Literal["local", "global", "hybrid"] = "hybrid"
    region: str = Field(default="global", min_length=2, max_length=32)
    protocol_hint: str = "ASTM"
    vendor_id: str | None = None
    product_id: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    device_class: str | None = None
    is_non_oem: bool = False


class DeviceScanResponse(BaseModel):
    identity: str
    protocol: str
    device_class: str
    confidence: float
    driver_candidates: list[dict[str, str]]
    install_plan: list[str]
    transport: dict[str, str | int]
    connectivity_profile: dict[str, str | int]
    quick_link: dict[str, str | bool | int]


class OnboardingExecuteRequest(DeviceScanRequest):
    device_id: str = Field(min_length=1)
    connector_type: Literal["tcp", "serial"]
    host: str | None = None
    port: int | None = None
    path: str | None = None
    baudrate: int = 9600
    vendor: str = "unknown"
    device_type: str = "unknown"
    dry_run: bool = False
    min_confidence: float = Field(default=0.7, ge=0.5, le=0.99)
    allow_generic_driver: bool = False


class OnboardingExecuteResponse(BaseModel):
    status: Literal["planned", "registered"]
    device_id: str
    scan: DeviceScanResponse


@app.get("/health")
def health() -> dict[str, str | dict[str, str]]:
    container = _get_container()
    result = container.health_service.check()
    return {"status": result.status, "version": result.version, "checks": result.checks}


@app.get("/metrics")
def metrics() -> dict:
    container = _get_container()
    return container.metrics.get_all_metrics()


@app.get("/traces")
def traces(limit: int = 50) -> list[str]:
    container = _get_container()
    return container.tracer.get_recent_traces(limit=limit)


@app.post("/devices/register")
def register_device(payload: RegisterDeviceRequest, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    try:
        return container.device_service.register_device(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        logger.warning(
            "Device registration failed",
            extra={"device_id": payload.device_id, "error": str(exc)},
        )
        raise HTTPException(status_code=400, detail="Invalid device configuration") from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error registering device",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@app.get("/devices")
def list_devices(_auth: Auth) -> list[dict]:
    container = _get_container()
    return [
        {"device_id": d.device_id, "is_connected": d.is_connected}
        for d in container.device_service.list_devices()
    ]


@app.get("/registry")
def list_registry(_auth: Auth) -> list[dict]:
    container = _get_container()
    return [
        {
            "device_id": item.device_id,
            "device_type": item.device_type,
            "vendor": item.vendor,
            "protocol": item.protocol,
            "connection": item.connection,
        }
        for item in container.device_service.list_registry()
    ]


@app.post("/devices/onboarding/scan", response_model=DeviceScanResponse)
def scan_device_onboarding(payload: DeviceScanRequest, _auth: Auth) -> DeviceScanResponse:
    container = _get_container()
    scan = container.device_service.scan_device(
        os_name=payload.os_name,
        supports_wireless=payload.supports_wireless,
        required_mbps=payload.required_mbps,
        max_latency_ms=payload.max_latency_ms,
        distance_meters=payload.distance_meters,
        deployment_target=payload.deployment_target,
        region=payload.region,
        protocol_hint=payload.protocol_hint,
        vendor_id=payload.vendor_id,
        product_id=payload.product_id,
        manufacturer=payload.manufacturer,
        model=payload.model,
        device_class=payload.device_class,
        is_non_oem=payload.is_non_oem,
    )
    return DeviceScanResponse(
        identity=scan.identity,
        protocol=scan.protocol,
        device_class=scan.device_class,
        confidence=scan.confidence,
        driver_candidates=scan.driver_candidates,
        install_plan=scan.install_plan,
        transport=scan.transport,
        connectivity_profile=scan.connectivity_profile,
        quick_link=scan.quick_link,
    )


@app.post("/devices/onboarding/execute", response_model=OnboardingExecuteResponse)
def execute_device_onboarding(
    payload: OnboardingExecuteRequest, _auth: Auth
) -> OnboardingExecuteResponse:
    container = _get_container()
    scan = container.device_service.scan_device(
        os_name=payload.os_name,
        supports_wireless=payload.supports_wireless,
        required_mbps=payload.required_mbps,
        max_latency_ms=payload.max_latency_ms,
        distance_meters=payload.distance_meters,
        deployment_target=payload.deployment_target,
        region=payload.region,
        protocol_hint=payload.protocol_hint,
        vendor_id=payload.vendor_id,
        product_id=payload.product_id,
        manufacturer=payload.manufacturer,
        model=payload.model,
        device_class=payload.device_class,
        is_non_oem=payload.is_non_oem,
    )
    try:
        result = container.device_service.execute_onboarding(
            device_id=payload.device_id,
            connector_type=payload.connector_type,
            host=payload.host,
            port=payload.port,
            path=payload.path,
            baudrate=payload.baudrate,
            vendor=payload.vendor,
            device_type=payload.device_type,
            scan=scan,
            dry_run=payload.dry_run,
            min_confidence=payload.min_confidence,
            allow_generic_driver=payload.allow_generic_driver,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error during onboarding",
            extra={"device_id": payload.device_id},
        )
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    if result.status == "planned":
        container.query_service.add_audit_event(
            event_type="device_onboarding_planned",
            payload={
                "device_id": payload.device_id,
                "protocol": scan.protocol,
                "confidence": scan.confidence,
                "transport": scan.transport,
            },
        )

    return OnboardingExecuteResponse(
        status=result.status,
        device_id=result.device_id,
        scan=DeviceScanResponse(
            identity=scan.identity,
            protocol=scan.protocol,
            device_class=scan.device_class,
            confidence=scan.confidence,
            driver_candidates=scan.driver_candidates,
            install_plan=scan.install_plan,
            transport=scan.transport,
            connectivity_profile=scan.connectivity_profile,
            quick_link=scan.quick_link,
        ),
    )


@app.post("/devices/{device_id}/command")
def send_device_command(device_id: str, payload: CommandRequest, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    try:
        return container.device_service.send_command(device_id, payload.command)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found") from None
    except Exception as exc:
        container.device_service.emit_command_error(device_id, exc)
        raise HTTPException(status_code=400, detail="Failed to send command") from exc


@app.post("/devices/{device_id}/routing")
def set_device_routing(
    device_id: str, payload: RoutingPolicyRequest, _auth: Auth
) -> dict[str, str]:
    container = _get_container()
    return container.ingest_service.set_device_routing(device_id, payload.policy)


@app.post("/mode")
def set_mode(payload: ModeRequest, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    result = container.mode_service.set(payload.mode)
    return {"status": "updated", "mode": result.mode}


@app.get("/mode")
def get_mode(_auth: Auth) -> dict[str, str]:
    container = _get_container()
    result = container.mode_service.get_status()
    return {"mode": result.mode}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest, _auth: Auth) -> IngestResponse:
    container = _get_container()
    result = await container.ingest_service.ingest(
        device_id=payload.device_id,
        patient_id=payload.patient_id,
        chunk=payload.chunk,
        vendor=payload.vendor,
        barcode=payload.barcode,
        current_mode=container.mode_service.get(),
    )
    return IngestResponse(status=result.status, processed=result.processed, results=result.results)


@app.post("/edge/sync")
async def sync_edge_buffer(_auth: Auth) -> dict[str, int]:
    container = _get_container()
    return await container.ingest_service.sync_edge_buffer()


@app.get("/alerts")
def list_alerts(_auth: Auth, limit: int = 100, offset: int = 0) -> list[dict[str, str]]:
    container = _get_container()
    return container.query_service.list_alerts(limit=limit, offset=offset)


@app.get("/results")
def list_results(_auth: Auth, limit: int = 100, offset: int = 0) -> list[dict]:
    container = _get_container()
    return container.query_service.list_results(limit=limit, offset=offset)


@app.get("/logs")
def list_logs(_auth: Auth, limit: int = 100, offset: int = 0) -> list[dict]:
    container = _get_container()
    return container.query_service.list_logs(limit=limit, offset=offset)


@app.get("/audit")
def list_audit(_auth: Auth, limit: int = 100, offset: int = 0) -> list[dict]:
    container = _get_container()
    return container.query_service.list_audit_trail(limit=limit, offset=offset)


@app.get("/offline-queue")
def list_offline_queue(_auth: Auth, limit: int = 100, offset: int = 0) -> list[dict]:
    container = _get_container()
    return container.query_service.list_offline_queue(limit=limit, offset=offset)
