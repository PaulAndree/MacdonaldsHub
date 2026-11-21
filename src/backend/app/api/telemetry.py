"""Outermost middleware: correlation id, actor and result on a span and a structured log."""

import logging
import time
from collections.abc import Awaitable, Callable

from opentelemetry.trace import Span, Status, StatusCode, Tracer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability import log_event, new_correlation_id, result_for_status

ACCESS_LOG = logging.getLogger("app.access")
HEADER = "x-correlation-id"


class TelemetryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, tracer: Tracer) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._tracer = tracer

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = new_correlation_id(request.headers.get(HEADER))
        started = time.perf_counter()
        status = 500
        with self._tracer.start_as_current_span("http.request") as span:
            try:
                response = await call_next(request)
                status = response.status_code
                response.headers[HEADER] = correlation_id
                return response
            finally:
                user = getattr(request.state, "user", None)
                actor = user.identifier if user is not None else "anonymous"
                result = result_for_status(status)
                self._finish(span, request, correlation_id, actor, status, result)
                log_event(
                    ACCESS_LOG,
                    event="http.request",
                    correlation_id=correlation_id,
                    actor=actor,
                    method=request.method,
                    path=request.url.path,  # query string deliberately not logged
                    status=status,
                    result=result,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )

    @staticmethod
    def _finish(
        span: Span, request: Request, correlation_id: str, actor: str, status: int, result: str
    ) -> None:
        span.set_attribute("app.correlation_id", correlation_id)
        span.set_attribute("app.actor", actor)
        span.set_attribute("app.result", result)
        span.set_attribute("http.request.method", request.method)
        span.set_attribute("url.path", request.url.path)
        span.set_attribute("http.response.status_code", status)
        if status >= 500:
            span.set_status(Status(StatusCode.ERROR))
