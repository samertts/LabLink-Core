from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DeviceRegistration:
    device_id: str
    device_type: str
    vendor: str
    protocol: str
    connection: dict[str, Any]


class DeviceRegistry:
    """In-memory registry for all onboarded devices and connection metadata."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceRegistration] = {}

    def upsert(self, registration: DeviceRegistration) -> None:
        self._devices[registration.device_id] = registration

    def get(self, device_id: str) -> DeviceRegistration | None:
        return self._devices.get(device_id)

    def list_all(self) -> list[DeviceRegistration]:
        return list(self._devices.values())

    def remove(self, device_id: str) -> None:
        self._devices.pop(device_id, None)
