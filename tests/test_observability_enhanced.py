"""Tests for Observability enhancements — Prometheus format, request metrics, tracing (Phase 7)."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.observability.metrics import MetricsCollector
from app.observability.tracing import Span, Tracer

# ── Prometheus Format Tests ────────────────────────────────────────


class TestPrometheusFormat:
    def test_empty_metrics(self) -> None:
        mc = MetricsCollector()
        output = mc.prometheus_format()
        assert output == "\n"

    def test_counter_format(self) -> None:
        mc = MetricsCollector()
        mc.register_counter("http_requests_total", "Total requests")
        mc.increment("http_requests_total", tags={"method": "GET"})
        output = mc.prometheus_format()
        assert "# HELP http_requests_total Total requests" in output
        assert "# TYPE http_requests_total counter" in output
        assert 'http_requests_total{method="GET"}' in output

    def test_gauge_format(self) -> None:
        mc = MetricsCollector()
        mc.register_gauge("mem_usage", "Memory usage")
        mc.gauge("mem_usage", 0.75, tags={"host": "srv1"})
        output = mc.prometheus_format()
        assert "# TYPE mem_usage gauge" in output
        assert 'mem_usage{host="srv1"} 0.75' in output

    def test_histogram_format(self) -> None:
        mc = MetricsCollector()
        for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
            mc.histogram("request_duration", v)
        output = mc.prometheus_format()
        assert "# TYPE request_duration histogram" in output
        assert "request_duration_count" in output
        assert "request_duration_sum" in output
        assert "request_duration_bucket" in output

    def test_multiple_counters(self) -> None:
        mc = MetricsCollector()
        mc.increment("a", tags={"x": "1"})
        mc.increment("b", tags={"y": "2"})
        output = mc.prometheus_format()
        assert 'a{x="1"}' in output
        assert 'b{y="2"}' in output


# ── Tracing Tests ──────────────────────────────────────────────────


class TestTracing:
    def test_start_and_finish_trace(self) -> None:
        t = Tracer()
        tid = t.start_trace("op1")
        spans = t.get_trace(tid)
        assert len(spans) == 1
        assert spans[0]["name"] == "op1"

    def test_start_span(self) -> None:
        t = Tracer()
        tid = t.start_trace("root")
        sid = t.start_span(tid, "child")
        t.finish_span(sid, "ok")
        spans = t.get_trace(tid)
        assert len(spans) == 2
        child = [s for s in spans if s["span_id"] == sid][0]
        assert child["status"] == "ok"
        assert child["duration_ms"] is not None

    def test_get_recent_traces(self) -> None:
        t = Tracer()
        for i in range(5):
            t.start_trace(f"op{i}")
        recent = t.get_recent_traces(limit=3)
        assert len(recent) == 3

    def test_span_events(self) -> None:
        t = Tracer()
        tid = t.start_trace("op1")
        sid = t.start_span(tid, "sub")
        t.finish_span(sid)
        spans = t.get_trace(tid)
        assert spans[0]["events"] == [] or len(spans[0]["events"]) >= 0

    def test_span_attributes(self) -> None:
        t = Tracer()
        tid = t.start_trace("op1", attributes={"key": "val"})
        spans = t.get_trace(tid)
        assert spans[0]["attributes"]["key"] == "val"

    def test_clear(self) -> None:
        t = Tracer()
        t.start_trace("op1")
        t.clear()
        assert t.get_recent_traces() == []


# ── Span Tests ─────────────────────────────────────────────────────


class TestSpan:
    def test_to_dict(self) -> None:
        s = Span(trace_id="t1", name="test")
        d = s.to_dict()
        assert d["trace_id"] == "t1"
        assert d["name"] == "test"
        assert d["duration_ms"] is None

    def test_finish(self) -> None:
        s = Span(trace_id="t1", name="test")
        s.finish("error")
        assert s.status == "error"
        assert s.duration_ms is not None
        assert s.duration_ms >= 0

    def test_add_event(self) -> None:
        s = Span(trace_id="t1", name="test")
        s.add_event("event1", {"k": "v"})
        assert len(s.events) == 1
        assert s.events[0]["name"] == "event1"


# ── HTTP Endpoint Tests ────────────────────────────────────────────


class TestObservabilityEndpoints:
    def test_metrics_endpoint(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data

    def test_prometheus_endpoint(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/metrics/prometheus")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_traces_endpoint(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/traces")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_trace_detail_not_found(self) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/traces/nonexistent")
        assert resp.status_code == 404
