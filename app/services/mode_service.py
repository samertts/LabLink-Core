from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from app.core.modes import CommunicationMode

logger = logging.getLogger("lablink.services.mode")


@dataclass(frozen=True)
class ModeStatus:
    mode: str


class ModeService:
    """Thread-safe communication mode management."""

    def __init__(self, initial: CommunicationMode = CommunicationMode.HYBRID) -> None:
        self._mode: CommunicationMode = initial
        self._lock = threading.Lock()

    def get(self) -> CommunicationMode:
        with self._lock:
            return self._mode

    def set(self, mode: CommunicationMode) -> ModeStatus:
        with self._lock:
            self._mode = mode
        logger.info("Communication mode changed to %s", mode.value)
        return ModeStatus(mode=mode.value)

    def get_status(self) -> ModeStatus:
        return ModeStatus(mode=self.get().value)
