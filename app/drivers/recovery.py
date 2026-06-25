"""Driver recovery strategies."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.drivers.errors import DriverError, RecoveryAction

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RecoveryAttempt:
    """Record of a single recovery attempt."""

    action: RecoveryAction
    timestamp: float = field(default_factory=time.time)
    success: bool = False
    message: str = ""


class RecoveryStrategy:
    """Configurable recovery strategy for driver errors.

    Implements a circuit-breaker pattern with configurable thresholds
    and escalating recovery actions.
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        max_reconnect_attempts: int = 5,
        circuit_breaker_threshold: int = 10,
        circuit_breaker_reset_seconds: float = 60.0,
    ) -> None:
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._max_reconnect = max_reconnect_attempts
        self._circuit_threshold = circuit_breaker_threshold
        self._circuit_reset = circuit_breaker_reset_seconds
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at = 0.0
        self._history: list[RecoveryAttempt] = []
        self._action_handlers: dict[RecoveryAction, Callable[[], bool]] = {}

    @property
    def is_circuit_open(self) -> bool:
        if not self._circuit_open:
            return False
        if time.time() - self._circuit_opened_at > self._circuit_reset:
            self._circuit_open = False
            self._consecutive_failures = 0
            logger.info("Circuit breaker reset")
            return False
        return True

    def register_handler(self, action: RecoveryAction, handler: Callable[[], bool]) -> None:
        self._action_handlers[action] = handler

    def handle_error(self, error: DriverError) -> RecoveryAction:
        """Determine and execute the appropriate recovery action."""
        self._consecutive_failures += 1

        if self._consecutive_failures >= self._circuit_threshold:
            self._circuit_open = True
            self._circuit_opened_at = time.time()
            logger.warning(
                "Circuit breaker opened after %d consecutive failures",
                self._consecutive_failures,
            )
            return RecoveryAction.DISABLE

        if self.is_circuit_open:
            return RecoveryAction.DISABLE

        if not error.recoverable:
            self._record(RecoveryAction.ESCALATE, False, "Non-recoverable error")
            return RecoveryAction.ESCALATE

        action = self._select_action(error)
        success = self._execute(action)
        self._record(action, success, error.args[0] if error.args else "")

        if success:
            self._consecutive_failures = 0

        return action

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at = 0.0

    def _select_action(self, error: DriverError) -> RecoveryAction:
        if self._consecutive_failures <= self._max_retries:
            return RecoveryAction.RETRY
        if self._consecutive_failures <= self._max_reconnect:
            return RecoveryAction.RECONNECT
        return RecoveryAction.RESTART_DRIVER

    def _execute(self, action: RecoveryAction) -> bool:
        handler = self._action_handlers.get(action)
        if handler:
            try:
                return handler()
            except Exception as exc:
                logger.error("Recovery handler for %s failed: %s", action.value, exc)
                return False
        return False

    def _record(self, action: RecoveryAction, success: bool, message: str) -> None:
        self._history.append(RecoveryAttempt(action=action, success=success, message=message))
        if len(self._history) > 100:
            self._history = self._history[-100:]

    def get_history(self, limit: int = 10) -> list[RecoveryAttempt]:
        return list(reversed(self._history[-limit:]))

    def get_stats(self) -> dict[str, Any]:
        total = len(self._history)
        successes = sum(1 for a in self._history if a.success)
        return {
            "total_attempts": total,
            "successes": successes,
            "failures": total - successes,
            "consecutive_failures": self._consecutive_failures,
            "circuit_open": self.is_circuit_open,
        }
