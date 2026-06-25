from __future__ import annotations

import pytest

from app.core.connection_pool import ConnectionPool
from app.core.device_manager import DeviceManager
from app.storage.db import InMemoryDB
from app.storage.result_repository import LogRepository, ResultRepository


class FakeConnector:
    """Lightweight mock connector for unit tests."""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.is_connected = False
        self.connected = False
        self.last_payload = b""

    def connect(self) -> None:
        self.connected = True
        self.is_connected = True

    def disconnect(self) -> None:
        self.connected = False
        self.is_connected = False

    def send_command(self, payload: bytes) -> None:
        self.last_payload = payload


class DummyDeviceManager(DeviceManager):
    """DeviceManager that uses FakeConnector instead of real connectors."""

    def _build_connector(self, config: dict):  # type: ignore[override]
        return FakeConnector(config["device_id"])


@pytest.fixture
def fake_connector() -> type[FakeConnector]:
    return FakeConnector


@pytest.fixture
def dummy_device_manager() -> DummyDeviceManager:
    return DummyDeviceManager(pool=ConnectionPool())


@pytest.fixture
def in_memory_db() -> InMemoryDB:
    return InMemoryDB()


@pytest.fixture
def result_repository(in_memory_db: InMemoryDB) -> ResultRepository:
    return ResultRepository(db=in_memory_db)


@pytest.fixture
def log_repository(in_memory_db: InMemoryDB) -> LogRepository:
    return LogRepository(db=in_memory_db)
