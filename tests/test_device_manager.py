from app.core.connection_pool import ConnectionPool
from app.core.device_manager import DeviceManager


class FakeConnector:
    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False


class DummyDeviceManager(DeviceManager):
    def _build_connector(self, config: dict):  # type: ignore[override]
        return FakeConnector(config["device_id"])


def test_device_manager_adds_device_to_pool() -> None:
    manager = DummyDeviceManager(pool=ConnectionPool())
    connector = manager.add_device({"device_id": "DEV-1", "type": "serial"})

    assert connector.connected is True
    assert manager.pool.get("DEV-1") is connector
