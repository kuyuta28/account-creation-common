"""
tracing.py — OpenTelemetry FastAPI middleware for distributed tracing.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from common.logging.context import set_trace_info, get_request_id
from common.tracing import get_tracer


class TracingMiddleware(BaseHTTPMiddleware):
    """Create OTel span for each HTTP request."""

    async def dispatch(self, request: Request, call_next):
        tracer = get_tracer("common")

        span_name = f"HTTP {request.method} {request.url.path}"
        request_id = get_request_id()

        with tracer.start_as_current_span(span_name) as span:
            # Add span attributes
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.route", request.url.path)
            span.set_attribute("http.host", request.url.hostname or "")
            if request_id:
                span.set_attribute("request.id", request_id)

            # Process request
            response = await call_next(request)

            # Record response status
            span.set_attribute("http.status_code", response.status_code)

            return response


def add_tracing_middleware(app) -> None:
    """Add tracing middleware to FastAPI app. Call after request_id middleware."""
    app.add_middleware(TracingMiddleware)
