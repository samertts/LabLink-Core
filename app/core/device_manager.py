from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.connectors.base import BaseConnector, SerialConnector, TCPConnector
from app.core.connection_pool import ConnectionPool


@dataclass(slots=True)
class DeviceConfig:
    device_id: str
    connection_type: Literal["serial", "tcp"]
    path: str | None = None
    baudrate: int = 9600
    host: str | None = None
    port: int | None = None
    encoding: str = "utf-8"


class DeviceManager:
    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self.pool = pool or ConnectionPool()

    def add_device(self, config: DeviceConfig) -> BaseConnector:
        connector: BaseConnector
        if config.connection_type == "serial":
            if not config.path:
                raise ValueError("Serial config requires path")
            connector = SerialConnector(
                config.device_id,
                path=config.path,
                baudrate=config.baudrate,
                encoding=config.encoding,
            )
        elif config.connection_type == "tcp":
            if not config.host or config.port is None:
                raise ValueError("TCP config requires host and port")
            connector = TCPConnector(
                config.device_id,
                host=config.host,
                port=config.port,
                encoding=config.encoding,
            )
        else:
            raise ValueError(f"Unsupported connection type: {config.connection_type}")

        self.pool.add(connector)
        connector.connect()
        return connector

    def remove_device(self, device_id: str) -> None:
        self.pool.remove(device_id)
