from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector, SerialConnector, TCPConnector
from app.core.connection_pool import ConnectionPool


class DeviceManager:
    """Creates, tracks, and controls connectors for all onboarded devices."""

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self.pool = pool or ConnectionPool()

    def add_device(self, config: dict[str, Any]) -> BaseConnector:
        connector = self._build_connector(config)
        connector.connect()
        self.pool.add(connector)
        return connector

    def remove_device(self, device_id: str) -> None:
        self.pool.remove(device_id)

    def list_devices(self) -> list[BaseConnector]:
        return self.pool.all()

    def shutdown(self) -> None:
        self.pool.shutdown()

    def _build_connector(self, config: dict[str, Any]) -> BaseConnector:
        connector_type = str(config["type"]).lower()
        device_id = str(config["device_id"])

        if connector_type == "serial":
            return SerialConnector(
                device_id=device_id,
                path=str(config["path"]),
                baudrate=int(config.get("baudrate", 9600)),
            )

        if connector_type == "tcp":
            return TCPConnector(
                device_id=device_id,
                host=str(config["host"]),
                port=int(config["port"]),
                reconnect_delay_seconds=float(config.get("reconnect_delay_seconds", 1.0)),
            )

        raise ValueError(f"Unsupported connector type: {connector_type}")
