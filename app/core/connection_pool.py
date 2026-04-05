from __future__ import annotations

from app.connectors.base import BaseConnector


class ConnectionPool:
    """Keeps active connector instances keyed by device ID."""

    def __init__(self) -> None:
        self._connections: dict[str, BaseConnector] = {}

    def add(self, connector: BaseConnector) -> None:
        self._connections[connector.device_id] = connector

    def get(self, device_id: str) -> BaseConnector | None:
        return self._connections.get(device_id)

    def remove(self, device_id: str) -> None:
        existing = self._connections.pop(device_id, None)
        if existing is not None:
            existing.disconnect()

    def all(self) -> list[BaseConnector]:
        return list(self._connections.values())

    def send_to(self, device_id: str, payload: bytes) -> None:
        connector = self._connections.get(device_id)
        if connector is None:
            raise KeyError(f"Device not found: {device_id}")
        connector.send_command(payload)

    def broadcast(self, payload: bytes) -> None:
        for connector in self._connections.values():
            connector.send_command(payload)

    def shutdown(self) -> None:
        for connector in self._connections.values():
            connector.disconnect()
        self._connections.clear()
