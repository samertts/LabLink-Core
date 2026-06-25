from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("lablink.tracing")


@dataclass
class Span:
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    trace_id: str = ""
    name: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def finish(self, status: str = "ok") -> None:
        self.end_time = time.monotonic()
        self.status = status

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append(
            {
                "name": name,
                "attributes": attributes or {},
                "timestamp": time.time(),
            }
        )

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    """In-process distributed tracing infrastructure.

    Stores traces in memory.  Designed for future OpenTelemetry
    integration without external coupling.
    """

    def __init__(self, max_traces: int = 1000) -> None:
        self._lock = threading.Lock()
        self._traces: dict[str, list[Span]] = {}
        self._active: dict[str, Span] = {}
        self._max_traces = max_traces

    def start_trace(self, name: str, attributes: dict[str, Any] | None = None) -> str:
        trace_id = str(uuid.uuid4())[:12]
        span = Span(trace_id=trace_id, name=name, attributes=attributes or {})
        with self._lock:
            self._traces[trace_id] = [span]
            self._active[span.span_id] = span
        return trace_id

    def start_span(self, trace_id: str, name: str, attributes: dict[str, Any] | None = None) -> str:
        span = Span(trace_id=trace_id, name=name, attributes=attributes or {})
        with self._lock:
            if trace_id in self._traces:
                self._traces[trace_id].append(span)
            self._active[span.span_id] = span
        return span.span_id

    def finish_span(self, span_id: str, status: str = "ok") -> None:
        with self._lock:
            span = self._active.pop(span_id, None)
        if span:
            span.finish(status)

    def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            spans = self._traces.get(trace_id, [])
        return [s.to_dict() for s in spans]

    def get_recent_traces(self, limit: int = 50) -> list[str]:
        with self._lock:
            return list(self._traces.keys())[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()
            self._active.clear()
