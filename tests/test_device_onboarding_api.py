from fastapi.testclient import TestClient

import app.main as main
from app.core.connection_pool import ConnectionPool
from app.core.device_manager import DeviceManager
from app.security.auth import DEFAULT_API_KEY


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


def test_scan_endpoint_returns_plan() -> None:
    client = TestClient(main.app)
    headers = {"x-api-key": DEFAULT_API_KEY}

    response = client.post(
        "/devices/onboarding/scan",
        json={
            "os_name": "linux",
            "supports_wireless": True,
            "required_mbps": 200,
            "max_latency_ms": 20,
            "distance_meters": 10,
            "protocol_hint": "astm",
            "manufacturer": "Sysmex",
            "model": "XN",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["protocol"] == "ASTM"
    assert body["transport"]["technology"] == "wifi-6e"
    assert body["connectivity_profile"]["topology"] == "local-primary-global-failover"
    assert body["quick_link"]["profile"] == "quick-link"
    assert len(body["install_plan"]) >= 4


def test_scan_endpoint_enables_non_oem_quick_link_profile() -> None:
    client = TestClient(main.app)
    headers = {"x-api-key": DEFAULT_API_KEY}

    response = client.post(
        "/devices/onboarding/scan",
        json={
            "os_name": "linux",
            "supports_wireless": True,
            "required_mbps": 70,
            "max_latency_ms": 30,
            "distance_meters": 15,
            "protocol_hint": "bluetooth",
            "is_non_oem": True,
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["quick_link"]["compatibility_mode"] == "extended-generic"
    assert body["quick_link"]["wireless_boost"] is True


def test_execute_endpoint_registers_device(monkeypatch) -> None:
    monkeypatch.setattr(main, "device_manager", DummyDeviceManager(pool=ConnectionPool()))

    client = TestClient(main.app)
    headers = {"x-api-key": DEFAULT_API_KEY}
    response = client.post(
        "/devices/onboarding/execute",
        json={
            "device_id": "DEV-EXEC-1",
            "connector_type": "serial",
            "path": "/dev/ttyUSB0",
            "os_name": "linux",
            "supports_wireless": False,
            "required_mbps": 50,
            "max_latency_ms": 15,
            "distance_meters": 5,
            "vendor_id": "0ABC",
            "product_id": "00FE",
            "model": "XN-1000",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "registered"
    assert payload["device_id"] == "DEV-EXEC-1"


def test_execute_endpoint_validates_tcp_requirements(monkeypatch) -> None:
    monkeypatch.setattr(main, "device_manager", DummyDeviceManager(pool=ConnectionPool()))

    client = TestClient(main.app)
    headers = {"x-api-key": DEFAULT_API_KEY}

    response = client.post(
        "/devices/onboarding/execute",
        json={
            "device_id": "DEV-EXEC-2",
            "connector_type": "tcp",
            "os_name": "linux",
            "supports_wireless": True,
            "required_mbps": 100,
            "max_latency_ms": 10,
            "distance_meters": 5,
            "vendor_id": "0ABC",
            "product_id": "00FE",
            "model": "XN-1000",
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert "host and port" in response.json()["detail"]


def test_execute_endpoint_supports_dry_run_mode(monkeypatch) -> None:
    monkeypatch.setattr(main, "device_manager", DummyDeviceManager(pool=ConnectionPool()))

    client = TestClient(main.app)
    headers = {"x-api-key": DEFAULT_API_KEY}
    response = client.post(
        "/devices/onboarding/execute",
        json={
            "device_id": "DEV-EXEC-DRY",
            "connector_type": "serial",
            "path": "/dev/ttyUSB0",
            "os_name": "linux",
            "supports_wireless": False,
            "required_mbps": 20,
            "max_latency_ms": 20,
            "distance_meters": 5,
            "vendor_id": "0ABC",
            "product_id": "00FE",
            "model": "XN-1000",
            "dry_run": True,
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "planned"
