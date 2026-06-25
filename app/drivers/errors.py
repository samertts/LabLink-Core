"""Structured error types for the Driver SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RecoveryAction(Enum):
    """Possible recovery actions after a driver error."""

    NONE = "none"
    RETRY = "retry"
    RECONNECT = "reconnect"
    RESTART_DRIVER = "restart_driver"
    ESCALATE = "escalate"
    DISABLE = "disable"


@dataclass(frozen=True, slots=True)
class DriverWarning:
    """A non-fatal warning from a driver."""

    code: str
    message: str
    details: dict = field(default_factory=dict)
    recovery_action: RecoveryAction = RecoveryAction.NONE


class DriverError(Exception):
    """Structured error from a device driver.

    Attributes:
        code: Machine-readable error code (e.g. ``"CONNECTION_TIMEOUT"``).
        device_id: The device that caused the error.
        recovery_action: Suggested recovery action.
        details: Additional context.
        recoverable: Whether automatic recovery is possible.
    """

    def __init__(
        self,
        message: str,
        code: str = "DRIVER_ERROR",
        device_id: str = "",
        recovery_action: RecoveryAction = RecoveryAction.RETRY,
        details: dict | None = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.device_id = device_id
        self.recovery_action = recovery_action
        self.details = details or {}
        self.recoverable = recoverable

    def to_dict(self) -> dict:
        return {
            "error": str(self),
            "code": self.code,
            "device_id": self.device_id,
            "recovery_action": self.recovery_action.value,
            "recoverable": self.recoverable,
            "details": self.details,
        }


class ConnectionError(DriverError):
    """Connection-related error."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message, code="CONNECTION_ERROR", recovery_action=RecoveryAction.RECONNECT, **kwargs)


class TimeoutError(DriverError):
    """Timeout error."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message, code="TIMEOUT", recovery_action=RecoveryAction.RETRY, **kwargs)


class ProtocolError(DriverError):
    """Protocol parsing/handling error."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message, code="PROTOCOL_ERROR", recovery_action=RecoveryAction.RETRY, recoverable=False, **kwargs)


class AuthenticationError(DriverError):
    """Authentication/authorization error."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message, code="AUTH_ERROR", recovery_action=RecoveryAction.ESCALATE, recoverable=False, **kwargs)


class DataError(DriverError):
    """Data integrity or validation error."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message, code="DATA_ERROR", recovery_action=RecoveryAction.RETRY, **kwargs)
