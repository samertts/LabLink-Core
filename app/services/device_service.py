from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.alerting import AlertManager
from app.core.device_manager import DeviceManager
from app.core.device_onboarding import DeviceFingerprint, DeviceOnboardingDirector
from app.events.base import EventBus
from app.events.domain import AlertRaised, DeviceConnected, DeviceRegistered
from app.observability.metrics import MetricsCollector

logger = logging.getLogger("lablink.services.device")


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    is_connected: bool


@dataclass(frozen=True)
class RegistryEntry:
    device_id: str
    device_type: str
    vendor: str
    protocol: str
    connection: dict[str, Any]


@dataclass(frozen=True)
class ScanResult:
    identity: str
    protocol: str
    device_class: str
    confidence: float
    driver_candidates: list[dict[str, str]]
    install_plan: list[str]
    transport: dict[str, str | int]
    connectivity_profile: dict[str, str | int]
    quick_link: dict[str, str | bool | int]


@dataclass(frozen=True)
class OnboardingResult:
    status: str
    device_id: str
    scan: ScanResult


class DeviceService:
    """Encapsulates all device-related business logic."""

    def __init__(
        self,
        device_manager: DeviceManager,
        onboarding_director: DeviceOnboardingDirector,
        alerts: AlertManager,
        event_bus: EventBus | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._device_manager = device_manager
        self._onboarding_director = onboarding_director
        self._alerts = alerts
        self._event_bus = event_bus
        self._metrics = metrics

    def register_device(self, config: dict[str, Any]) -> dict[str, str]:
        self._device_manager.add_device(config)
        device_id = str(config["device_id"])

        if self._metrics:
            self._metrics.increment("device.registered")
        if self._event_bus:
            self._event_bus.publish(
                DeviceRegistered(
                    device_id=device_id,
                    vendor=config.get("vendor", "unknown"),
                    device_type=config.get("device_type", "unknown"),
                    protocol=config.get("protocol", "ASTM"),
                    source="device_service",
                )
            )

        return {"status": "registered", "device_id": device_id}

    def list_devices(self) -> list[DeviceInfo]:
        return [
            DeviceInfo(device_id=d.device_id, is_connected=d.is_connected)
            for d in self._device_manager.list_devices()
        ]

    def list_registry(self) -> list[RegistryEntry]:
        return [
            RegistryEntry(
                device_id=item.device_id,
                device_type=item.device_type,
                vendor=item.vendor,
                protocol=item.protocol,
                connection=item.connection,
            )
            for item in self._device_manager.list_registry()
        ]

    def send_command(self, device_id: str, command: str) -> dict[str, str]:
        self._device_manager.send_command(device_id, command)
        if self._metrics:
            self._metrics.increment("device.command_sent", tags={"device_id": device_id})
        return {"status": "sent", "device_id": device_id}

    def emit_command_error(self, device_id: str, error: Exception) -> None:
        self._alerts.emit(
            severity="error",
            message=f"Command failed for {device_id}",
            device_id=device_id,
        )
        if self._event_bus:
            self._event_bus.publish(
                AlertRaised(severity="error", message=f"Command failed for {device_id}", device_id=device_id, source="device_service")
            )
        if self._metrics:
            self._metrics.increment("device.command_error", tags={"device_id": device_id})
        logger.warning("Command failed", extra={"device_id": device_id, "error": str(error)})

    def scan_device(
        self,
        *,
        os_name: str,
        supports_wireless: bool,
        required_mbps: int,
        max_latency_ms: int,
        distance_meters: int,
        deployment_target: str,
        region: str,
        protocol_hint: str,
        vendor_id: str | None = None,
        product_id: str | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        device_class: str | None = None,
        is_non_oem: bool = False,
    ) -> ScanResult:
        identity = self._onboarding_director.identify_device(
            DeviceFingerprint(
                vendor_id=vendor_id,
                product_id=product_id,
                manufacturer=manufacturer,
                model=model,
                device_class=device_class,
                protocol_hint=protocol_hint,
            )
        )
        drivers = self._onboarding_director.driver_candidates(os_name, identity["protocol"])
        plan = self._onboarding_director.install_plan(os_name, identity["protocol"])
        transport = self._onboarding_director.recommend_transport(
            supports_wireless=supports_wireless,
            required_mbps=required_mbps,
            max_latency_ms=max_latency_ms,
            distance_meters=distance_meters,
        )
        connectivity_profile = self._onboarding_director.connectivity_profile(
            deployment_target=deployment_target,
            region=region,
            max_latency_ms=max_latency_ms,
        )
        quick_link = self._onboarding_director.quick_link_profile(
            os_name=os_name,
            protocol=str(identity["protocol"]),
            supports_wireless=supports_wireless,
            is_non_oem=is_non_oem,
        )
        return ScanResult(
            identity=str(identity["identity"]),
            protocol=str(identity["protocol"]),
            device_class=str(identity["device_class"]),
            confidence=float(identity["confidence"]),
            driver_candidates=drivers,
            install_plan=plan,
            transport=transport,
            connectivity_profile=connectivity_profile,
            quick_link=quick_link,
        )

    def execute_onboarding(
        self,
        *,
        device_id: str,
        connector_type: str,
        host: str | None,
        port: int | None,
        path: str | None,
        baudrate: int,
        vendor: str,
        device_type: str,
        scan: ScanResult,
        dry_run: bool = False,
        min_confidence: float = 0.7,
        allow_generic_driver: bool = False,
    ) -> OnboardingResult:
        if scan.confidence < min_confidence:
            raise ValueError(
                f"device confidence {scan.confidence:.2f} is below required threshold {min_confidence:.2f}"
            )

        uses_generic = any(item["source"] == "os-default" for item in scan.driver_candidates)
        if uses_generic and not allow_generic_driver:
            raise ValueError("generic driver requires explicit approval via allow_generic_driver=true")

        config: dict[str, Any] = {
            "device_id": device_id,
            "type": connector_type,
            "vendor": vendor,
            "device_type": device_type,
            "protocol": scan.protocol,
            "baudrate": baudrate,
        }
        if connector_type == "tcp":
            if host is None or port is None:
                raise ValueError("host and port are required for tcp connector")
            config["host"] = host
            config["port"] = port
        else:
            if path is None:
                raise ValueError("path is required for serial connector")
            config["path"] = path

        if dry_run:
            return OnboardingResult(status="planned", device_id=device_id, scan=scan)

        self._device_manager.add_device(config)

        if self._event_bus:
            self._event_bus.publish(
                DeviceConnected(device_id=device_id, connector_type=connector_type, source="device_service")
            )

        return OnboardingResult(status="registered", device_id=device_id, scan=scan)

    def shutdown(self) -> None:
        self._device_manager.shutdown()
