"""Request-level observability middleware — HTTP metrics + tracing."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.metrics import MetricsCollector
from app.observability.tracing import Tracer


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Emits per-request metrics and traces for every HTTP call.

    Metrics emitted:
    - ``http_requests_total`` (counter) — tagged by method, path, status
    - ``http_request_duration_seconds`` (histogram) — tagged by method, path, status
    - ``http_requests_in_flight`` (gauge) — current concurrent requests
    """

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._metrics: MetricsCollector | None = None
        self._tracer: Tracer | None = None
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        try:
            from app.main import _get_container
            container = _get_container()
            self._metrics = container.metrics
            self._tracer = container.tracer
            self._metrics.register_counter("http_requests_total", "Total HTTP requests")
            self._metrics.register_counter("http_request_errors_total", "Total HTTP error responses (4xx/5xx)")
            self._metrics.register_gauge("http_requests_in_flight", "Requests currently in flight")
            self._metrics.register_counter("http_request_duration_seconds", "Request duration in seconds")
            self._initialized = True
        except Exception:
            pass

    async def dispatch(self, request: Request, call_next: object) -> Response:
        self._ensure_init()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:12])
        path = request.url.path
        method = request.method

        if self._metrics:
            self._metrics.increment("http_requests_in_flight")
            self._metrics.increment("http_requests_total", tags={"method": method, "path": path, "status": "pending"})

        trace_id: str | None = None
        span_id: str | None = None
        if self._tracer:
            trace_id = self._tracer.start_trace(f"HTTP {method} {path}", attributes={"request_id": request_id, "method": method, "path": path})
            span_id = self._tracer.start_span(trace_id, "request_handler")

        start = time.monotonic()
        status_code = 500
        try:
            response: Response = await call_next(request)  # type: ignore[operator]
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.monotonic() - start
            status_str = str(status_code)
            if self._metrics:
                self._metrics.decrement("http_requests_in_flight")
                self._metrics.increment("http_requests_total", tags={"method": method, "path": path, "status": status_str})
                self._metrics.histogram("http_request_duration_seconds", duration, tags={"method": method, "path": path})
                if status_code >= 400:
                    self._metrics.increment("http_request_errors_total", tags={"method": method, "path": path, "status": status_str})
            if self._tracer and span_id:
                self._tracer.finish_span(span_id, status="error" if status_code >= 500 else "ok")
