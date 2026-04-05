from __future__ import annotations

from typing import Any


class EdgeAgentBuffer:
    """Local buffer for branch/offline mode with explicit sync drain."""

    def __init__(self) -> None:
        self._buffer: list[dict[str, Any]] = []

    def enqueue(self, payload: dict[str, Any]) -> None:
        self._buffer.append(payload)

    def pending(self) -> int:
        return len(self._buffer)

    def drain(self) -> list[dict[str, Any]]:
        items = list(self._buffer)
        self._buffer.clear()
        return items
