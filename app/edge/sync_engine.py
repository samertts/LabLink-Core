from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(slots=True)
class SyncItem:
    item_id: str
    device_id: str
    payload: dict[str, Any]
    version: int
    updated_at: datetime


class SyncEngine:
    """Edge->Cloud sync queue with retries and simple conflict resolution."""

    def __init__(self) -> None:
        self._queue: dict[str, SyncItem] = {}

    def stage(self, *, item_id: str, device_id: str, payload: dict[str, Any], version: int = 1) -> None:
        incoming = SyncItem(
            item_id=item_id,
            device_id=device_id,
            payload=payload,
            version=version,
            updated_at=datetime.now(timezone.utc),
        )
        existing = self._queue.get(item_id)
        if existing is None or incoming.version >= existing.version:
            self._queue[item_id] = incoming

    def pending(self) -> int:
        return len(self._queue)

    async def sync(self, sender: Callable[[dict[str, Any]], Any]) -> dict[str, int]:
        sent = 0
        failed = 0
        for item_id in list(self._queue.keys()):
            item = self._queue[item_id]
            try:
                result = await sender(item.payload)
                if isinstance(result, dict) and result.get("status") == "failed":
                    failed += 1
                    continue
                sent += 1
                self._queue.pop(item_id, None)
            except Exception:
                failed += 1
        return {"sent": sent, "failed": failed, "remaining": len(self._queue)}
