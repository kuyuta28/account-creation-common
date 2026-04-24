"""
propagators.py — W3C trace context propagation.
"""
from __future__ import annotations

from common.logging.context import TraceInfo, set_trace_info


def propagate_trace(traceparent: str | None) -> TraceInfo | None:
    """Parse and set trace context from W3C traceparent header."""
    if not traceparent:
        return None
    info = TraceInfo.from_traceparent(traceparent)
    if info:
        set_trace_info(info)
    return info
