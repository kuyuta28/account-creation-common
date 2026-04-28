"""account-creation-common — Shared core utilities for all services."""

# Logging & Tracing
from .logging import (
    get_request_id,
    get_trace_info,
    set_request_id,
    set_trace_info,
    request_id_context,
    trace_context,
    TraceInfo,
    JSONFormatter,
    structured_log,
    log_info_structured,
    log_warning_structured,
    log_error_structured,
    log_debug_structured,
)

from .tracing import (
    init_tracing,
    get_tracer,
    add_span_attributes,
    get_current_trace_id,
    get_current_span_id,
    load_tracing_config,
    TracingConfig,
    propagate_trace,
)

from .middleware import (
    add_request_id_middleware,
    add_tracing_middleware,
)

from .clients import (
    InternalClient,
    set_internal_key,
    get_internal_key,
)

from .context import (
    AppContext,
    init_app_context,
    get_app_context,
    lifespan_context,
)

__all__ = [
    # Logging
    "get_request_id",
    "set_request_id",
    "get_trace_info",
    "set_trace_info",
    "request_id_context",
    "trace_context",
    "TraceInfo",
    "JSONFormatter",
    "structured_log",
    "log_info_structured",
    "log_warning_structured",
    "log_error_structured",
    "log_debug_structured",
    # Tracing
    "init_tracing",
    "get_tracer",
    "add_span_attributes",
    "get_current_trace_id",
    "get_current_span_id",
    "load_tracing_config",
    "TracingConfig",
    "propagate_trace",
    # Middleware
    "add_request_id_middleware",
    "add_tracing_middleware",
    # Clients
    "InternalClient",
    "set_internal_key",
    "get_internal_key",
    # Context
    "AppContext",
    "init_app_context",
    "get_app_context",
    "lifespan_context",
]