from __future__ import annotations

import pytest

from app.core.alerting import AlertManager
from app.core.connection_pool import ConnectionPool
from app.core.device_manager import DeviceManager
from app.core.device_onboarding import DeviceOnboardingDirector
from app.services.device_service import DeviceService, ScanResult


class FakeConnector:
    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.is_connected = False

    def connect(self) -> None:
        self.is_connected = True

    def disconnect(self) -> None:
        self.is_connected = False

    def send_command(self, payload: bytes) -> None:
        _ = payload


class DummyDeviceManager(DeviceManager):
    def _build_connector(self, config: dict):  # type: ignore[override]
        return FakeConnector(config["device_id"])


@pytest.fixture
def device_service() -> DeviceService:
    dm = DummyDeviceManager(pool=ConnectionPool())
    return DeviceService(
        device_manager=dm,
        onboarding_director=DeviceOnboardingDirector(),
        alerts=AlertManager(),
    )


class TestDeviceServiceRegister:
    def test_register_device_returns_status(self, device_service: DeviceService) -> None:
        result = device_service.register_device(
            {"device_id": "D1", "type": "serial", "path": "/dev/ttyUSB0"}
        )
        assert result["status"] == "registered"
        assert result["device_id"] == "D1"

    def test_register_device_lists_it(self, device_service: DeviceService) -> None:
        device_service.register_device(
            {"device_id": "D2", "type": "serial", "path": "/dev/ttyUSB0"}
        )
        devices = device_service.list_devices()
        assert any(d.device_id == "D2" for d in devices)


class TestDeviceServiceListDevices:
    def test_empty_list(self, device_service: DeviceService) -> None:
        assert device_service.list_devices() == []

    def test_lists_registered_devices(self, device_service: DeviceService) -> None:
        device_service.register_device(
            {"device_id": "D1", "type": "serial", "path": "/dev/ttyUSB0"}
        )
        devices = device_service.list_devices()
        assert len(devices) == 1
        assert devices[0].device_id == "D1"
        assert devices[0].is_connected is True


class TestDeviceServiceListRegistry:
    def test_empty_registry(self, device_service: DeviceService) -> None:
        assert device_service.list_registry() == []

    def test_lists_registered_entries(self, device_service: DeviceService) -> None:
        device_service.register_device(
            {"device_id": "D1", "type": "serial", "path": "/dev/ttyUSB0", "vendor": "Sysmex"}
        )
        entries = device_service.list_registry()
        assert len(entries) == 1
        assert entries[0].device_id == "D1"
        assert entries[0].vendor == "Sysmex"


class TestDeviceServiceCommand:
    def test_send_command(self, device_service: DeviceService) -> None:
        device_service.register_device(
            {"device_id": "D1", "type": "serial", "path": "/dev/ttyUSB0"}
        )
        result = device_service.send_command("D1", "Q")
        assert result["status"] == "sent"
        assert result["device_id"] == "D1"

    def test_send_command_unknown_device(self, device_service: DeviceService) -> None:
        with pytest.raises(KeyError):
            device_service.send_command("UNKNOWN", "Q")


class TestDeviceServiceScan:
    def test_scan_returns_scan_result(self, device_service: DeviceService) -> None:
        result = device_service.scan_device(
            os_name="linux",
            supports_wireless=True,
            required_mbps=200,
            max_latency_ms=20,
            distance_meters=10,
            deployment_target="hybrid",
            region="global",
            protocol_hint="astm",
            manufacturer="Sysmex",
            model="XN",
        )
        assert isinstance(result, ScanResult)
        assert result.protocol == "ASTM"
        assert result.confidence > 0

    def test_scan_transport_recommendation(self, device_service: DeviceService) -> None:
        result = device_service.scan_device(
            os_name="linux",
            supports_wireless=True,
            required_mbps=200,
            max_latency_ms=20,
            distance_meters=10,
            deployment_target="hybrid",
            region="global",
            protocol_hint="astm",
        )
        assert "technology" in result.transport


class TestDeviceServiceOnboarding:
    def test_execute_registers_device(self, device_service: DeviceService) -> None:
        scan = device_service.scan_device(
            os_name="linux",
            supports_wireless=False,
            required_mbps=50,
            max_latency_ms=15,
            distance_meters=5,
            deployment_target="hybrid",
            region="global",
            protocol_hint="astm",
            vendor_id="0ABC",
            product_id="00FE",
            model="XN-1000",
        )
        result = device_service.execute_onboarding(
            device_id="DEV-1",
            connector_type="serial",
            host=None,
            port=None,
            path="/dev/ttyUSB0",
            baudrate=9600,
            vendor="Sysmex",
            device_type="analyzer",
            scan=scan,
        )
        assert result.status == "registered"
        assert result.device_id == "DEV-1"

    def test_execute_dry_run(self, device_service: DeviceService) -> None:
        scan = device_service.scan_device(
            os_name="linux",
            supports_wireless=False,
            required_mbps=50,
            max_latency_ms=15,
            distance_meters=5,
            deployment_target="hybrid",
            region="global",
            protocol_hint="astm",
            vendor_id="0ABC",
            product_id="00FE",
            model="XN-1000",
        )
        result = device_service.execute_onboarding(
            device_id="DEV-DRY",
            connector_type="serial",
            host=None,
            port=None,
            path="/dev/ttyUSB0",
            baudrate=9600,
            vendor="Sysmex",
            device_type="analyzer",
            scan=scan,
            dry_run=True,
        )
        assert result.status == "planned"

    def test_execute_rejects_low_confidence(self, device_service: DeviceService) -> None:
        scan = ScanResult(
            identity="unknown",
            protocol="unknown",
            device_class="unknown",
            confidence=0.3,
            driver_candidates=[],
            install_plan=[],
            transport={},
            connectivity_profile={},
            quick_link={},
        )
        with pytest.raises(ValueError, match="below required threshold"):
            device_service.execute_onboarding(
                device_id="DEV-LOW",
                connector_type="serial",
                host=None,
                port=None,
                path="/dev/ttyUSB0",
                baudrate=9600,
                vendor="unknown",
                device_type="unknown",
                scan=scan,
                min_confidence=0.7,
            )

    def test_execute_rejects_generic_driver(self, device_service: DeviceService) -> None:
        scan = ScanResult(
            identity="unknown",
            protocol="unknown",
            device_class="unknown",
            confidence=0.9,
            driver_candidates=[{"source": "os-default", "name": "generic"}],
            install_plan=[],
            transport={},
            connectivity_profile={},
            quick_link={},
        )
        with pytest.raises(ValueError, match="generic driver"):
            device_service.execute_onboarding(
                device_id="DEV-GEN",
                connector_type="serial",
                host=None,
                port=None,
                path="/dev/ttyUSB0",
                baudrate=9600,
                vendor="unknown",
                device_type="unknown",
                scan=scan,
                allow_generic_driver=False,
            )

    def test_execute_tcp_requires_host_port(self, device_service: DeviceService) -> None:
        scan = device_service.scan_device(
            os_name="linux",
            supports_wireless=True,
            required_mbps=100,
            max_latency_ms=10,
            distance_meters=5,
            deployment_target="hybrid",
            region="global",
            protocol_hint="astm",
            vendor_id="0ABC",
            product_id="00FE",
            model="XN-1000",
        )
        with pytest.raises(ValueError, match="host and port"):
            device_service.execute_onboarding(
                device_id="DEV-TCP",
                connector_type="tcp",
                host=None,
                port=None,
                path=None,
                baudrate=9600,
                vendor="Sysmex",
                device_type="analyzer",
                scan=scan,
            )

    def test_execute_serial_requires_path(self, device_service: DeviceService) -> None:
        scan = device_service.scan_device(
            os_name="linux",
            supports_wireless=False,
            required_mbps=50,
            max_latency_ms=15,
            distance_meters=5,
            deployment_target="hybrid",
            region="global",
            protocol_hint="astm",
            vendor_id="0ABC",
            product_id="00FE",
            model="XN-1000",
        )
        with pytest.raises(ValueError, match="path is required"):
            device_service.execute_onboarding(
                device_id="DEV-SER",
                connector_type="serial",
                host=None,
                port=None,
                path=None,
                baudrate=9600,
                vendor="Sysmex",
                device_type="analyzer",
                scan=scan,
            )
