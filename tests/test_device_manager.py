from app.core.connection_pool import ConnectionPool
from app.core.device_manager import DeviceManager


class FakeConnector:
    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.connected = False
        self.last_payload = b""
        self.is_connected = False

    def connect(self) -> None:
        self.connected = True
        self.is_connected = True

    def disconnect(self) -> None:
        self.connected = False
        self.is_connected = False

    def send_command(self, payload: bytes) -> None:
        self.last_payload = payload


class DummyDeviceManager(DeviceManager):
    def _build_connector(self, config: dict):  # type: ignore[override]
        return FakeConnector(config["device_id"])


def test_device_manager_adds_device_to_pool() -> None:
    manager = DummyDeviceManager(pool=ConnectionPool())
    connector = manager.add_device({"device_id": "DEV-1", "type": "serial"})

    assert connector.connected is True
    assert manager.pool.get("DEV-1") is connector


def test_device_manager_registry_and_command() -> None:
    manager = DummyDeviceManager(pool=ConnectionPool())
    connector = manager.add_device(
        {
            "device_id": "DEV-2",
            "type": "tcp",
            "vendor": "Sysmex",
            "device_type": "CBC",
            "protocol": "ASTM",
            "host": "127.0.0.1",
            "port": 5000,
        }
    )

    manager.send_command("DEV-2", "REQUEST_RESULTS")
    registry = manager.list_registry()

    assert connector.last_payload == b"REQUEST_RESULTS"
    assert registry[0].vendor == "Sysmex"
