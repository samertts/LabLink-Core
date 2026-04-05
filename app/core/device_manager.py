from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector, SerialConnector, TCPConnector
from app.core.connection_pool import ConnectionPool
from app.core.device_registry import DeviceRegistration, DeviceRegistry


class DeviceManager:
    """Creates, tracks, and controls connectors for all onboarded devices."""

    def __init__(
        self,
        pool: ConnectionPool | None = None,
        registry: DeviceRegistry | None = None,
    ) -> None:
        self.pool = pool or ConnectionPool()
        self.registry = registry or DeviceRegistry()

    def add_device(self, config: dict[str, Any]) -> BaseConnector:
        connector = self._build_connector(config)
        connector.connect()
        self.pool.add(connector)
        self.registry.upsert(
            DeviceRegistration(
                device_id=str(config["device_id"]),
                device_type=str(config.get("device_type", config.get("type", "unknown"))),
                vendor=str(config.get("vendor", "unknown")),
                protocol=str(config.get("protocol", "ASTM")),
                connection={k: v for k, v in config.items() if k not in {"vendor", "device_type", "protocol"}},
            )
        )
        return connector

    def remove_device(self, device_id: str) -> None:
        self.pool.remove(device_id)
        self.registry.remove(device_id)

    def send_command(self, device_id: str, command: str) -> None:
        self.pool.send_to(device_id, command.encode("ascii"))

    def broadcast_command(self, command: str) -> None:
        self.pool.broadcast(command.encode("ascii"))

    def list_devices(self) -> list[BaseConnector]:
        return self.pool.all()

    def list_registry(self) -> list[DeviceRegistration]:
        return self.registry.list_all()

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
