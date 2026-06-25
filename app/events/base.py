from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("lablink.events")


@dataclass(frozen=True)
class EventMetadata:
    """Immutable metadata attached to every event."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str = ""
    source: str = ""
    version: int = 1


class Event:
    """Base class for all domain events.

    Subclass this to define typed domain events.  The ``event_type`` class
    attribute is used for routing and logging.
    """

    event_type: str = "base"

    def __init__(self, **data: Any) -> None:
        self.data = data
        self.metadata = EventMetadata(
            correlation_id=data.pop("correlation_id", ""),
            source=data.pop("source", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "metadata": {
                "event_id": self.metadata.event_id,
                "timestamp": self.metadata.timestamp,
                "correlation_id": self.metadata.correlation_id,
                "source": self.metadata.source,
                "version": self.metadata.version,
            },
        }


EventHandler = Callable[[Event], Coroutine[Any, Any, None] | None]


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Supports both sync and async handlers.  Handlers are invoked in
    registration order.  Exceptions in handlers are logged but do not
    prevent other handlers from executing.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = threading.Lock()
        self._handlers: dict[str, list[EventHandler]] = {}
        self._history: list[Event] = []
        self._max_history = max_history
        self._interceptors: list[Callable[[Event], Event]] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def add_interceptor(self, interceptor: Callable[[Event], Event]) -> None:
        with self._lock:
            self._interceptors.append(interceptor)

    def publish(self, event: Event) -> None:
        with self._lock:
            for interceptor in self._interceptors:
                event = interceptor(event)
            self._record_history(event)
            handlers = list(self._handlers.get(event.event_type, []))
            wildcard_handlers = list(self._handlers.get("*", []))

        all_handlers = handlers + wildcard_handlers
        for handler in all_handlers:
            try:
                result = handler(event)
                if result is not None and hasattr(result, "__await__"):
                    logger.warning(
                        "Async handler %s registered on sync publish; "
                        "use publish_async for async handlers",
                        handler,
                    )
            except Exception:
                logger.exception(
                    "Event handler %s failed for event %s",
                    handler,
                    event.event_type,
                )

    async def publish_async(self, event: Event) -> None:
        with self._lock:
            for interceptor in self._interceptors:
                event = interceptor(event)
            self._record_history(event)
            handlers = list(self._handlers.get(event.event_type, []))
            wildcard_handlers = list(self._handlers.get("*", []))

        all_handlers = handlers + wildcard_handlers
        for handler in all_handlers:
            try:
                result = handler(event)
                if result is not None and hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception(
                    "Event handler %s failed for event %s",
                    handler,
                    event.event_type,
                )

    def get_history(self, event_type: str | None = None, limit: int = 100) -> list[Event]:
        with self._lock:
            events = self._history
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            return list(events[-limit:])

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()

    def _record_history(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def subscriber_count(self, event_type: str) -> int:
        with self._lock:
            return len(self._handlers.get(event_type, []))
