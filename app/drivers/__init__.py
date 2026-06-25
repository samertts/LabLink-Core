"""Driver SDK for LabLink Platform.

Provides the BaseDriver abstraction, device metadata, capabilities,
health monitoring, diagnostics, error handling, and recovery for
laboratory device drivers.
"""

from app.drivers.base import (
    BaseDriver,
    ConnectionState,
    DeviceCapabilities,
    DeviceMetadata,
    DriverConfig,
)
from app.drivers.diagnostics import DiagnosticReport, DriverDiagnostics
from app.drivers.errors import DriverError, DriverWarning, RecoveryAction
from app.drivers.health import DeviceHealth, HealthCheckResult
from app.drivers.manager import DriverManager
from app.drivers.recovery import RecoveryStrategy

__all__ = [
    "BaseDriver",
    "ConnectionState",
    "DeviceCapabilities",
    "DeviceHealth",
    "DeviceMetadata",
    "DiagnosticReport",
    "DriverConfig",
    "DriverDiagnostics",
    "DriverError",
    "DriverManager",
    "DriverWarning",
    "HealthCheckResult",
    "RecoveryAction",
    "RecoveryStrategy",
]
