from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import PlainTextResponse

from app.config.settings import get_settings
from app.core.modes import CommunicationMode
from app.log_config.setup import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.pipeline.normalizer import NormalizedResult
from app.security.auth import verify_api_key
from app.security.middleware import SecurityHeadersMiddleware
from app.security.models import Permission
from app.security.rbac import CurrentUser
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
    configure_logging(json_format=(settings.log_format == "json"))
    _container = create_service_container(settings)
    if settings.worker_enabled:
        _container.worker.start()
    _container.plugin_manager.startup()
    logger.info("LabLink Core started (v1.3.0)")
    yield
    logger.info("Shutting down LabLink Core...")
    _container.plugin_manager.shutdown()
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
app.add_middleware(SecurityHeadersMiddleware)

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


@app.get("/metrics/prometheus")
def metrics_prometheus() -> PlainTextResponse:
    container = _get_container()
    return PlainTextResponse(content=container.metrics.prometheus_format(), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/traces")
def traces(limit: int = 50) -> list[str]:
    container = _get_container()
    return container.tracer.get_recent_traces(limit=limit)


@app.get("/traces/{trace_id}")
def trace_detail(trace_id: str) -> list[dict]:
    container = _get_container()
    spans = container.tracer.get_trace(trace_id)
    if not spans:
        raise HTTPException(status_code=404, detail="Trace not found")
    return spans


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


# ── Plugin Management Endpoints ────────────────────────────────────


class PluginConfigRequest(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: str


@app.get("/plugins")
def list_plugins(_auth: Auth) -> list[dict]:
    container = _get_container()
    return container.plugin_manager.summary()


@app.get("/plugins/capabilities")
def list_plugin_capabilities(_auth: Auth) -> dict[str, list[str]]:
    container = _get_container()
    return container.plugin_manager.capabilities()


@app.get("/plugins/{name}")
def get_plugin(name: str, _auth: Auth) -> dict:
    container = _get_container()
    record = container.plugin_manager.registry.get_record(name)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return {
        "name": record.manifest.name,
        "version": record.manifest.version,
        "description": record.manifest.description,
        "author": record.manifest.author,
        "state": record.state.value,
        "error": record.error,
        "provides": record.plugin.capabilities(),
        "requires": record.manifest.requires,
        "activation_count": record.activation_count,
    }


@app.post("/plugins/{name}/activate")
def activate_plugin(name: str, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    try:
        container.plugin_manager.activate_plugin(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "activated", "plugin": name}


@app.post("/plugins/{name}/deactivate")
def deactivate_plugin(name: str, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    try:
        container.plugin_manager.deactivate_plugin(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found") from None
    return {"status": "deactivated", "plugin": name}


@app.post("/plugins/{name}/reload")
def reload_plugin(name: str, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    try:
        container.plugin_manager.reload_plugin(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found") from None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "reloaded", "plugin": name}


@app.get("/plugins/health")
def plugin_health(_auth: Auth) -> dict:
    container = _get_container()
    results = container.plugin_manager.health_checker.check_all()
    return {
        "overall": container.plugin_manager.health_checker.get_overall_status(),
        "plugins": [
            {
                "name": r.plugin_name,
                "status": r.status,
                "message": r.message,
                "duration_ms": round(r.duration_ms, 2),
            }
            for r in results
        ],
    }


@app.get("/plugins/{name}/health")
def plugin_health_single(name: str, _auth: Auth) -> dict:
    container = _get_container()
    result = container.plugin_manager.health_checker.check_plugin(name)
    return {
        "name": result.plugin_name,
        "status": result.status,
        "message": result.message,
        "details": result.details,
        "duration_ms": round(result.duration_ms, 2),
    }


@app.get("/plugins/{name}/config")
def get_plugin_config(name: str, _auth: Auth) -> dict:
    container = _get_container()
    if not container.plugin_manager.registry.has(name):
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return container.plugin_manager.get_plugin_config(name)


@app.put("/plugins/{name}/config")
def set_plugin_config(name: str, payload: PluginConfigRequest, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    if not container.plugin_manager.registry.has(name):
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    container.plugin_manager.set_plugin_config(name, payload.key, payload.value)
    return {"status": "updated", "plugin": name, "key": payload.key}


# ── Auth & RBAC Endpoints ─────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    password: str = Field(min_length=6, max_length=128)
    roles: list[str] | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    permissions: list[str] = Field(default_factory=list)
    description: str = ""


@app.post("/auth/login")
def login(payload: LoginRequest, request: Request) -> dict:
    from app.security.audit import AuditEventType, log_auth_event
    from app.security.models import get_security_store
    from app.security.passwords import verify_password
    from app.security.tokens import create_token_pair

    store = get_security_store()
    user = store.get_user_by_username(payload.username)
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")

    if user is None or not user.is_active:
        log_auth_event(AuditEventType.LOGIN_FAILURE, payload.username, ip_address=ip, user_agent=ua, success=False)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.locked_until and user.locked_until > time.time():
        log_auth_event(AuditEventType.LOGIN_FAILURE, payload.username, detail={"reason": "account_locked"}, ip_address=ip, user_agent=ua, success=False)
        raise HTTPException(status_code=423, detail="Account is locked")

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = time.time() + 900  # 15 min
            log_auth_event(AuditEventType.USER_LOCKED, user.user_id, ip_address=ip, user_agent=ua)
        log_auth_event(AuditEventType.LOGIN_FAILURE, user.user_id, ip_address=ip, user_agent=ua, success=False)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = time.time()

    tokens = create_token_pair(user.user_id, user.roles)
    log_auth_event(AuditEventType.LOGIN_SUCCESS, user.user_id, ip_address=ip, user_agent=ua)

    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
        "user": user.to_dict(),
    }


@app.post("/auth/register")
def register(payload: RegisterRequest, current_user: CurrentUser) -> dict:
    from app.security.audit import AuditEventType, log_auth_event
    from app.security.models import get_security_store
    from app.security.passwords import hash_password

    store = get_security_store()

    # Only admin can assign roles other than viewer
    if payload.roles and payload.roles != ["viewer"]:
        # If caller isn't admin, deny
        effective = store.get_effective_permissions(current_user)
        if Permission.SYSTEM_ADMIN not in effective:
            raise HTTPException(status_code=403, detail="Only admins can assign non-viewer roles")

    existing = store.get_user_by_username(payload.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = store.create_user(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        roles=payload.roles or ["viewer"],
    )
    log_auth_event(AuditEventType.USER_CREATED, current_user.user_id, target_id=user.user_id)
    return user.to_dict()


@app.post("/auth/refresh")
def refresh_token(refresh_token: str) -> dict:
    from app.security.audit import AuditEventType, log_auth_event
    from app.security.models import get_security_store
    from app.security.tokens import create_token_pair, decode_token

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    store = get_security_store()
    user = store.get_user(payload.get("sub", ""))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    tokens = create_token_pair(user.user_id, user.roles)
    log_auth_event(AuditEventType.TOKEN_REFRESH, user.user_id)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
    }


@app.get("/auth/me")
def get_me(user: CurrentUser) -> dict:
    from app.security.models import get_security_store
    store = get_security_store()
    return {
        **user.to_dict(),
        "permissions": sorted(p.value for p in store.get_effective_permissions(user)),
    }


@app.put("/auth/password")
def change_password(payload: ChangePasswordRequest, user: CurrentUser) -> dict[str, str]:
    from app.security.audit import AuditEventType, log_auth_event
    from app.security.models import get_security_store
    from app.security.passwords import hash_password, verify_password

    store = get_security_store()
    if not verify_password(payload.old_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    store.update_user(user.user_id, hashed_password=hash_password(payload.new_password))
    log_auth_event(AuditEventType.PASSWORD_CHANGED, user.user_id)
    return {"status": "password_changed"}


@app.get("/auth/users")
def list_users(user: CurrentUser) -> list[dict]:
    from app.security.models import get_security_store
    store = get_security_store()
    effective = store.get_effective_permissions(user)
    if Permission.USER_READ not in effective:
        raise HTTPException(status_code=403, detail="Missing permission: user:read")
    return [u.to_dict() for u in store.list_users()]


@app.post("/auth/roles")
def create_role(payload: CreateRoleRequest, user: CurrentUser) -> dict:
    from app.security.audit import AuditEventType, log_auth_event
    from app.security.models import Permission as Perm
    from app.security.models import get_security_store

    store = get_security_store()
    effective = store.get_effective_permissions(user)
    if Perm.ROLE_WRITE not in effective:
        raise HTTPException(status_code=403, detail="Missing permission: role:write")

    try:
        perms = {Perm(p) for p in payload.permissions}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {exc}") from exc

    role = store.create_role(name=payload.name, permissions=frozenset(perms), description=payload.description)
    log_auth_event(AuditEventType.ADMIN_ACTION, user.user_id, target_id=role.name, detail={"action": "create_role"})
    return role.to_dict()


@app.get("/auth/roles")
def list_roles(user: CurrentUser) -> list[dict]:
    from app.security.models import get_security_store
    store = get_security_store()
    return [r.to_dict() for r in store.list_roles()]


@app.get("/auth/audit")
def get_security_audit(user: CurrentUser, limit: int = 100) -> list[dict]:
    from app.security.audit import AuditEventType, get_audit_log
    from app.security.models import get_security_store

    store = get_security_store()
    effective = store.get_effective_permissions(user)
    if AuditEventType.AUDIT_READ not in {p.value for p in effective} and Permission.AUDIT_READ not in effective:
        raise HTTPException(status_code=403, detail="Missing permission: audit:read")
    log = get_audit_log()
    return [e.to_dict() for e in log.query(limit=limit)]


# ── Backup & Recovery Endpoints ────────────────────────────────────


class BackupCreateRequest(BaseModel):
    backup_type: Literal["full", "incremental", "snapshot"] = "full"
    tables: list[str] | None = None
    compression: Literal["none", "gzip"] = "none"


@app.get("/backups")
def list_backups(_auth: Auth) -> list[dict]:
    container = _get_container()
    return container.backup_engine.list_backups()


@app.get("/backups/summary")
def backup_summary(_auth: Auth) -> dict:
    container = _get_container()
    return container.backup_engine.summary()


@app.post("/backups")
def create_backup(payload: BackupCreateRequest, _auth: Auth) -> dict:
    from app.backup.models import BackupType
    container = _get_container()
    bt = BackupType(payload.backup_type)
    manifest = container.backup_engine.create_backup(backup_type=bt, tables=payload.tables, compression=payload.compression)
    return manifest.to_dict()


@app.get("/backups/{backup_id}")
def get_backup(backup_id: str, _auth: Auth) -> dict:
    container = _get_container()
    manifest = container.backup_engine.get_manifest(backup_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Backup '{backup_id}' not found")
    return manifest.to_dict()


@app.post("/backups/{backup_id}/restore")
def restore_backup(backup_id: str, _auth: Auth) -> dict:
    container = _get_container()
    result = container.backup_engine.restore_backup(backup_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.to_dict()


@app.post("/backups/{backup_id}/verify")
def verify_backup(backup_id: str, _auth: Auth) -> dict[str, bool]:
    container = _get_container()
    ok = container.backup_engine.verify_backup(backup_id)
    return {"verified": ok}


@app.delete("/backups/{backup_id}")
def delete_backup(backup_id: str, _auth: Auth) -> dict[str, str]:
    container = _get_container()
    deleted = container.backup_engine.delete_backup(backup_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Backup '{backup_id}' not found")
    return {"status": "deleted", "backup_id": backup_id}


@app.post("/backups/retention")
def enforce_retention(_auth: Auth) -> dict:
    container = _get_container()
    deleted = container.backup_engine.enforce_retention()
    return {"deleted": deleted, "count": len(deleted)}


# ── Multi-Tenancy Endpoints ───────────────────────────────────────


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9\-]+$")
    max_devices: int = Field(default=50, ge=1, le=10000)
    max_users: int = Field(default=20, ge=1, le=1000)
    tags: list[str] = Field(default_factory=list)


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    max_devices: int | None = None
    max_users: int | None = None
    settings: dict[str, str] | None = None
    tags: list[str] | None = None


@app.get("/tenants")
def list_tenants(_auth: Auth) -> list[dict]:
    from app.tenancy.store import get_tenant_store
    return [t.to_dict() for t in get_tenant_store().list_all()]


@app.get("/tenants/summary")
def tenant_summary(_auth: Auth) -> dict:
    from app.tenancy.store import get_tenant_store
    store = get_tenant_store()
    return {"total": store.count(), "active": store.count(active_only=True)}


@app.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: str, _auth: Auth) -> dict:
    from app.tenancy.store import get_tenant_store
    tenant = get_tenant_store().get(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    return tenant.to_dict()


@app.post("/tenants")
def create_tenant(payload: TenantCreateRequest, user: CurrentUser) -> dict:
    from app.tenancy.store import get_tenant_store
    store = get_tenant_store()
    # Only admins can create tenants
    from app.security.models import get_security_store
    sec_store = get_security_store()
    perms = sec_store.get_effective_permissions(user)
    if Permission.SYSTEM_ADMIN not in perms:
        raise HTTPException(status_code=403, detail="Only admins can create tenants")

    existing = store.get_by_slug(payload.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    tenant = store.create(
        name=payload.name,
        slug=payload.slug,
        max_devices=payload.max_devices,
        max_users=payload.max_users,
        tags=payload.tags,
    )
    return tenant.to_dict()


@app.put("/tenants/{tenant_id}")
def update_tenant(tenant_id: str, payload: TenantUpdateRequest, user: CurrentUser) -> dict:
    from app.tenancy.store import get_tenant_store
    store = get_tenant_store()
    from app.security.models import get_security_store
    sec_store = get_security_store()
    perms = sec_store.get_effective_permissions(user)
    if Permission.SYSTEM_ADMIN not in perms:
        raise HTTPException(status_code=403, detail="Only admins can update tenants")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    tenant = store.update(tenant_id, **updates)
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    return tenant.to_dict()


@app.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: str, user: CurrentUser) -> dict[str, str]:
    from app.tenancy.store import get_tenant_store
    store = get_tenant_store()
    from app.security.models import get_security_store
    sec_store = get_security_store()
    perms = sec_store.get_effective_permissions(user)
    if Permission.SYSTEM_ADMIN not in perms:
        raise HTTPException(status_code=403, detail="Only admins can delete tenants")

    if tenant_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default tenant")

    deleted = store.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    return {"status": "deleted", "tenant_id": tenant_id}


# ── AI Integration Layer Endpoints ─────────────────────────────────


class LogAnalysisRequest(BaseModel):
    logs: list[dict[str, Any]] = Field(default_factory=list)
    provider: str | None = None


class AnomalyDetectionRequest(BaseModel):
    values: list[float] = Field(default_factory=list)
    provider: str | None = None


class FailurePredictionRequest(BaseModel):
    device_history: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None


class PatternRecognitionRequest(BaseModel):
    data_points: list[float] = Field(default_factory=list)
    provider: str | None = None


class RootCauseRequest(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    provider: str | None = None


@app.get("/ai/providers")
def list_ai_providers(_auth: Auth) -> list[dict]:
    container = _get_container()
    return container.ai_engine.list_providers()


@app.get("/ai/summary")
def ai_summary(_auth: Auth) -> dict:
    container = _get_container()
    return container.ai_engine.summary()


@app.get("/ai/history")
def ai_history(_auth: Auth, limit: int = 50) -> list[dict]:
    container = _get_container()
    return container.ai_engine.get_history(limit=limit)


@app.post("/ai/analyze/logs")
def analyze_logs(payload: LogAnalysisRequest, _auth: Auth) -> dict:
    container = _get_container()
    response = container.ai_engine.analyze_logs(payload.logs, provider_name=payload.provider)
    return response.to_dict()


@app.post("/ai/analyze/anomalies")
def detect_anomalies(payload: AnomalyDetectionRequest, _auth: Auth) -> dict:
    container = _get_container()
    response = container.ai_engine.detect_anomalies(payload.values, provider_name=payload.provider)
    return response.to_dict()


@app.post("/ai/analyze/failures")
def predict_failures(payload: FailurePredictionRequest, _auth: Auth) -> dict:
    container = _get_container()
    response = container.ai_engine.predict_failure(payload.device_history, provider_name=payload.provider)
    return response.to_dict()


@app.post("/ai/analyze/patterns")
def recognize_patterns(payload: PatternRecognitionRequest, _auth: Auth) -> dict:
    container = _get_container()
    response = container.ai_engine.recognize_patterns(payload.data_points, provider_name=payload.provider)
    return response.to_dict()


@app.post("/ai/analyze/root-cause")
def root_cause(payload: RootCauseRequest, _auth: Auth) -> dict:
    container = _get_container()
    response = container.ai_engine.root_cause_analysis(payload.symptoms, provider_name=payload.provider)
    return response.to_dict()
