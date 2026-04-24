"""
context.py — Request-scoped context via contextvars.

Provides async-task-safe storage for request_id and trace context.
Each FastAPI request gets isolated context via ContextVar.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

# ── Request ID Context ─────────────────────────────────────────────────────────

request_id_context: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get current request ID from context, or empty string if not set."""
    return request_id_context.get()


def set_request_id(request_id: str) -> None:
    """Set request ID for current async task."""
    request_id_context.set(request_id)


# ── Trace Context ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TraceInfo:
    """W3C trace context info."""
    trace_id: str      # 32 hex chars
    span_id: str       # 16 hex chars
    trace_flags: str   # "00" (sampled) or "01" (not sampled)

    @property
    def traceparent(self) -> str:
        """Build W3C traceparent header value."""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    @classmethod
    def from_traceparent(cls, traceparent: str) -> TraceInfo | None:
        """Parse W3C traceparent header value."""
        try:
            version, trace_id, span_id, flags = traceparent.split("-")
            if len(trace_id) == 32 and len(span_id) == 16:
                return cls(trace_id=trace_id, span_id=span_id, trace_flags=flags)
        except (ValueError, IndexError):
            pass
        return None


trace_context: ContextVar[TraceInfo | None] = ContextVar("trace_context", default=None)


def get_trace_info() -> TraceInfo | None:
    """Get current trace context, or None if not set."""
    return trace_context.get()


def set_trace_info(info: TraceInfo) -> None:
    """Set trace info for current async task."""
    trace_context.set(info)
