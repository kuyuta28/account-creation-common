"""
request_id.py — FastAPI middleware for request ID extraction and propagation.
"""
from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from common.logging.context import set_request_id
from common.logging import get_trace_info, set_trace_info, TraceInfo


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Extract or generate request ID, store in contextvars, inject to response."""

    async def dispatch(self, request: Request, call_next):
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        # Extract traceparent header
        traceparent = request.headers.get("traceparent")
        if traceparent:
            trace_info = TraceInfo.from_traceparent(traceparent)
            if trace_info:
                set_trace_info(trace_info)

        # Process request
        response = await call_next(request)

        # Inject request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


def add_request_id_middleware(app) -> None:
    """Add request ID middleware to FastAPI app. Call once per app."""
    app.add_middleware(RequestIDMiddleware)