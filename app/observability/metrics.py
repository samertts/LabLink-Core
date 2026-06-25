from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("lablink.metrics")


@dataclass(frozen=True)
class MetricPoint:
    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """In-memory metrics collector.

    Stores counters, gauges, and histograms.  Designed for future
    Prometheus/OpenTelemetry integration without coupling to external
    libraries now.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._points: list[MetricPoint] = []
        self._max_points = 10000

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        key = self._make_key(name, tags)
        with self._lock:
            self._counters[key] += value
        self._record(name, self._counters[key], tags or {})

    def decrement(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        self.increment(name, -value, tags)

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        key = self._make_key(name, tags)
        with self._lock:
            self._gauges[key] = value
        self._record(name, value, tags or {})

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        key = self._make_key(name, tags)
        with self._lock:
            self._histograms[key].append(value)
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
        self._record(name, value, tags or {})

    def get_counter(self, name: str, tags: dict[str, str] | None = None) -> float:
        key = self._make_key(name, tags)
        with self._lock:
            return self._counters.get(key, 0.0)

    def get_gauge(self, name: str, tags: dict[str, str] | None = None) -> float | None:
        key = self._make_key(name, tags)
        with self._lock:
            return self._gauges.get(key)

    def get_histogram_stats(self, name: str, tags: dict[str, str] | None = None) -> dict[str, float]:
        key = self._make_key(name, tags)
        with self._lock:
            values = list(self._histograms.get(key, []))
        if not values:
            return {}
        values_sorted = sorted(values)
        n = len(values_sorted)
        return {
            "count": float(n),
            "min": values_sorted[0],
            "max": values_sorted[-1],
            "mean": sum(values_sorted) / n,
            "p50": values_sorted[n // 2],
            "p95": values_sorted[int(n * 0.95)] if n > 1 else values_sorted[0],
            "p99": values_sorted[int(n * 0.99)] if n > 1 else values_sorted[0],
        }

    def get_all_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: len(v) for k, v in self._histograms.items()},
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._points.clear()

    def _record(self, name: str, value: float, tags: dict[str, str]) -> None:
        point = MetricPoint(name=name, value=value, tags=tags)
        with self._lock:
            self._points.append(point)
            if len(self._points) > self._max_points:
                self._points = self._points[-self._max_points:]

    @staticmethod
    def _make_key(name: str, tags: dict[str, str] | None) -> str:
        if not tags:
            return name
        sorted_tags = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{sorted_tags}}}"
