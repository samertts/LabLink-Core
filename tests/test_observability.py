from __future__ import annotations

import threading

from app.observability.metrics import MetricsCollector


class TestMetricsCollector:
    def test_increment(self) -> None:
        m = MetricsCollector()
        m.increment("test.counter")
        m.increment("test.counter", 2.0)
        assert m.get_counter("test.counter") == 3.0

    def test_decrement(self) -> None:
        m = MetricsCollector()
        m.increment("c", 5.0)
        m.decrement("c", 2.0)
        assert m.get_counter("c") == 3.0

    def test_gauge(self) -> None:
        m = MetricsCollector()
        m.gauge("temp", 42.0)
        assert m.get_gauge("temp") == 42.0

    def test_histogram(self) -> None:
        m = MetricsCollector()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            m.histogram("latency", v)
        stats = m.get_histogram_stats("latency")
        assert stats["count"] == 5.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0

    def test_tags(self) -> None:
        m = MetricsCollector()
        m.increment("req", tags={"method": "GET"})
        m.increment("req", tags={"method": "POST"})
        assert m.get_counter("req", tags={"method": "GET"}) == 1.0
        assert m.get_counter("req", tags={"method": "POST"}) == 1.0

    def test_get_all_metrics(self) -> None:
        m = MetricsCollector()
        m.increment("a")
        m.gauge("b", 1.0)
        all_m = m.get_all_metrics()
        assert "counters" in all_m
        assert "gauges" in all_m

    def test_reset(self) -> None:
        m = MetricsCollector()
        m.increment("x")
        m.reset()
        assert m.get_counter("x") == 0.0

    def test_histogram_empty(self) -> None:
        m = MetricsCollector()
        stats = m.get_histogram_stats("nonexistent")
        assert stats == {}

    def test_thread_safety(self) -> None:
        m = MetricsCollector()

        def inc() -> None:
            for _ in range(100):
                m.increment("thread_test")

        threads = [threading.Thread(target=inc) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert m.get_counter("thread_test") == 400.0
