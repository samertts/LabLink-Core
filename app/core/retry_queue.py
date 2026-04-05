from __future__ import annotations

from collections import deque
from typing import Any


class RetryQueue:
    """Simple in-memory queue for offline/failed upstream deliveries."""

    def __init__(self) -> None:
        self._items: deque[dict[str, Any]] = deque()

    def enqueue(self, item: dict[str, Any]) -> None:
        self._items.append(item)

    def dequeue(self) -> dict[str, Any] | None:
        if not self._items:
            return None
        return self._items.popleft()

    def size(self) -> int:
        return len(self._items)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._items)
