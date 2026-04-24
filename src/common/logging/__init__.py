"""Logging module — structured JSON logs with request/trace context."""
from .context import (
    get_request_id,
    get_trace_info,
    request_id_context,
    set_request_id,
    set_trace_info,
    trace_context,
    TraceInfo,
)
from .structured import (
    JSONFormatter,
    log_debug_structured,
    log_error_structured,
    log_info_structured,
    log_warning_structured,
    structured_log,
)

__all__ = [
    # Context
    "request_id_context",
    "trace_context",
    "get_request_id",
    "set_request_id",
    "get_trace_info",
    "set_trace_info",
    "TraceInfo",
    # Structured logging
    "JSONFormatter",
    "structured_log",
    "log_info_structured",
    "log_warning_structured",
    "log_error_structured",
    "log_debug_structured",
]