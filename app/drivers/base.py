"""Core driver types: metadata, capabilities, connection state, config, and BaseDriver ABC."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state of a device driver."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    RECOVERING = "recovering"


@dataclass(frozen=True, slots=True)
class DeviceMetadata:
    """Static identification and manufacturer information for a device."""

    device_id: str
    vendor: str
    model: str
    serial_number: str = ""
    firmware_version: str = ""
    hardware_version: str = ""
    manufacture_date: str = ""
    device_class: str = "unknown"
    protocol: str = "ASTM"
    transport: str = "tcp"
    description: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.vendor} {self.model} ({self.device_id})"


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """Describes what a device can do."""

    supports_realtime: bool = True
    supports_batch: bool = False
    supports_bi_directional: bool = True
    supports_query: bool = False
    supports_calibration: bool = False
    supports_quality_control: bool = False
    max_concurrent_sessions: int = 1
    max_data_rate_bps: int = 0
    supported_protocols: tuple[str, ...] = ("ASTM",)
    supported_parameters: tuple[str, ...] = ()
    requires_patient_id: bool = True
    requires_operator_id: bool = False


@dataclass(slots=True)
class DriverConfig:
    """Runtime configuration for a driver instance."""

    connection_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    write_timeout_seconds: float = 10.0
    retry_count: int = 3
    retry_delay_seconds: float = 1.0
    health_check_interval_seconds: float = 30.0
    max_reconnect_attempts: int = 5
    reconnect_delay_seconds: float = 2.0
    buffer_size: int = 4096
    custom: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.custom.get(key, default)


class BaseDriver(ABC):
    """Abstract base class for all laboratory device drivers.

    A driver encapsulates the complete device integration: connection
    management, protocol handling, data interpretation, health monitoring,
    diagnostics, and error recovery.

    Lifecycle:
        __init__ → configure() → connect() → [read_data/write_command]* → disconnect() → cleanup()

    Drivers are loaded and managed by the ``DriverManager``. Each driver
    instance is associated with exactly one physical or logical device.
    """

    def __init__(self, metadata: DeviceMetadata, config: DriverConfig | None = None) -> None:
        self._metadata = metadata
        self._config = config or DriverConfig()
        self._state = ConnectionState.DISCONNECTED
        self._error_count = 0
        self._last_error: str | None = None
        self._ctx: dict[str, Any] = {}

    # ── Properties ──────────────────────────────────────────────────

    @property
    def metadata(self) -> DeviceMetadata:
        return self._metadata

    @property
    def device_id(self) -> str:
        return self._metadata.device_id

    @property
    def config(self) -> DriverConfig:
        return self._config

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state in (ConnectionState.CONNECTED, ConnectionState.READY, ConnectionState.BUSY)

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def last_error(self) -> str | None:
        return self._last_error

    # ── Capabilities (override in subclass) ─────────────────────────

    def capabilities(self) -> DeviceCapabilities:
        """Return the capabilities of this device."""
        return DeviceCapabilities()

    # ── Lifecycle hooks ─────────────────────────────────────────────

    def configure(self, config: DriverConfig) -> None:
        """Apply runtime configuration before connection."""
        self._config = config

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the device."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection to the device."""

    @abstractmethod
    def read_data(self) -> bytes:
        """Read raw data from the device.

        Returns:
            Raw bytes received from the device.

        Raises:
            DriverError: If the read fails.
        """

    @abstractmethod
    def write_data(self, data: bytes) -> None:
        """Write raw data to the device.

        Raises:
            DriverError: If the write fails.
        """

    def send_command(self, command: str) -> str:
        """Send a high-level command and return the response string.

        Default implementation encodes the command as bytes, writes it,
        reads the response, and decodes it. Subclasses may override for
        protocol-specific handling.
        """
        self.write_data(command.encode("utf-8"))
        raw = self.read_data()
        return raw.decode("utf-8", errors="replace")

    # ── Health ──────────────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """Perform a health check.

        Must return at least ``{"status": "healthy"|"degraded"|"unhealthy"}``.
        """
        return {
            "status": "healthy" if self.is_connected else "degraded",
            "state": self._state.value,
            "error_count": self._error_count,
            "device_id": self.device_id,
        }

    # ── Diagnostics ─────────────────────────────────────────────────

    def collect_diagnostics(self) -> dict[str, Any]:
        """Collect diagnostic information about the driver and device."""
        return {
            "device_id": self.device_id,
            "vendor": self._metadata.vendor,
            "model": self._metadata.model,
            "state": self._state.value,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "capabilities": {
                "realtime": self.capabilities().supports_realtime,
                "batch": self.capabilities().supports_batch,
                "protocols": list(self.capabilities().supported_protocols),
            },
        }

    # ── Error handling ──────────────────────────────────────────────

    def _record_error(self, message: str) -> None:
        self._error_count += 1
        self._last_error = message
        self._state = ConnectionState.ERROR
        logger.error("Driver %s error: %s", self.device_id, message)

    def _clear_error(self) -> None:
        self._last_error = None

    # ── State management ────────────────────────────────────────────

    def _set_state(self, state: ConnectionState) -> None:
        old = self._state
        self._state = state
        if old != state:
            logger.debug(
                "Driver %s state: %s → %s", self.device_id, old.value, state.value
            )

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} {self._metadata.display_name} "
            f"[{self._state.value}]>"
        )
