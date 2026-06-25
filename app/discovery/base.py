"""Base types for device discovery."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DiscoveryMethod(Enum):
    TCP_SCAN = "tcp_scan"
    SERIAL_SCAN = "serial_scan"
    USB_SCAN = "usb_scan"
    NETWORK_SCAN = "network_scan"
    MANUAL = "manual"


@dataclass(slots=True)
class DiscoveryConfig:
    tcp_host_range: str = "192.168.1.0/24"
    tcp_ports: tuple[int, ...] = (23, 4000, 4001, 5000, 8000, 9100)
    serial_ports: tuple[str, ...] = ("/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyS0")
    scan_timeout_seconds: float = 2.0
    max_concurrent: int = 50
    fingerprint_timeout: float = 5.0
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredDevice:
    device_id: str
    address: str
    port: int = 0
    transport: str = "tcp"
    method: DiscoveryMethod = DiscoveryMethod.TCP_SCAN
    vendor: str = "unknown"
    model: str = "unknown"
    protocol: str = "unknown"
    serial_number: str = ""
    firmware_version: str = ""
    is_online: bool = True
    response_time_ms: float = 0.0
    raw_response: bytes = b""
    capabilities: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "address": self.address,
            "port": self.port,
            "transport": self.transport,
            "method": self.method.value,
            "vendor": self.vendor,
            "model": self.model,
            "protocol": self.protocol,
            "serial_number": self.serial_number,
            "is_online": self.is_online,
            "response_time_ms": self.response_time_ms,
        }
