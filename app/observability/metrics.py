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
    """In-memory metrics collector with Prometheus exposition format.

    Stores counters, gauges, and histograms.  Emits Prometheus-compatible
    text exposition on ``prometheus_format()``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._points: list[MetricPoint] = []
        self._max_points = 10000
        self._counter_metadata: dict[str, str] = {}
        self._gauge_metadata: dict[str, str] = {}

    def register_counter(self, name: str, help_text: str = "") -> None:
        self._counter_metadata[name] = help_text

    def register_gauge(self, name: str, help_text: str = "") -> None:
        self._gauge_metadata[name] = help_text

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

    def prometheus_format(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines: list[str] = []

        with self._lock:
            # Counters
            for key, value in self._counters.items():
                base_name, labels = self._parse_key(key)
                help_text = self._counter_metadata.get(base_name, "")
                if help_text and not any(line.startswith(f"# HELP {base_name}") for line in lines):
                    lines.append(f"# HELP {base_name} {help_text}")
                    lines.append(f"# TYPE {base_name} counter")
                label_str = f"{{{labels}}}" if labels else ""
                lines.append(f"{base_name}{label_str} {value}")

            # Gauges
            for key, value in self._gauges.items():
                base_name, labels = self._parse_key(key)
                help_text = self._gauge_metadata.get(base_name, "")
                if help_text and not any(line.startswith(f"# HELP {base_name}") for line in lines):
                    lines.append(f"# HELP {base_name} {help_text}")
                    lines.append(f"# TYPE {base_name} gauge")
                label_str = f"{{{labels}}}" if labels else ""
                lines.append(f"{base_name}{label_str} {value}")

            # Histograms
            for key, values in self._histograms.items():
                base_name, labels = self._parse_key(key)
                if not values:
                    continue
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                label_str = f"{{{labels}}}" if labels else ""
                lines.append(f"# TYPE {base_name} histogram")
                lines.append(f"{base_name}_count{label_str} {n}")
                lines.append(f"{base_name}_sum{label_str} {sum(sorted_vals)}")
                for _pct, val in [(0.5, sorted_vals[n // 2]), (0.95, sorted_vals[int(n * 0.95)]), (0.99, sorted_vals[min(int(n * 0.99), n - 1)]), (1.0, sorted_vals[-1])]:
                    bucket_label = f'le="{val}"'
                    all_labels = f"{labels},{bucket_label}" if labels else bucket_label
                    lines.append(f"{base_name}_bucket{{{all_labels}}} {n}")

        return "\n".join(lines) + "\n"

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
        sorted_tags = ",".join(f'{k}="{v}"' for k, v in sorted(tags.items()))
        return f'{name}{{{sorted_tags}}}'

    @staticmethod
    def _parse_key(key: str) -> tuple[str, str]:
        """Split 'name{k="v",...}' into ('name', 'k="v",...')."""
        if "{" not in key:
            return key, ""
        idx = key.index("{")
        base = key[:idx]
        labels = key[idx + 1:-1] if key.endswith("}") else key[idx + 1:]
        return base, labels
