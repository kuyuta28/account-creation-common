"""
init.py — OpenTelemetry tracing initialization.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider

_log = logging.getLogger(__name__)

_tracer: "TracerProvider | None" = None


def init_tracing(service_name: str, enabled: bool = True) -> None:
    """Initialize OpenTelemetry tracing."""
    global _tracer

    if not enabled:
        _log.info("Tracing disabled for %s", service_name)
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.trace import set_tracer_provider

        resource = Resource(attributes={
            SERVICE_NAME: service_name,
        })
        _tracer = TracerProvider(resource=resource)

        # Console exporter for dev (logs spans to stdout)
        _tracer.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        set_tracer_provider(_tracer)
        _log.info("Tracing initialized for %s", service_name)

    except ImportError as e:
        # Demoted to debug: the OT SDK is an optional runtime dep, and
        # the dev stack intentionally doesn't ship it. Emitting this as
        # WARNING on every container boot drowned the actual logs.
        _log.debug("OpenTelemetry not installed: %s", e)
    except Exception as e:
        _log.error("Failed to init tracing: %s", e)


def get_tracer(name: str = "common"):
    """Get a tracer instance."""
    global _tracer

    if _tracer is not None:
        try:
            from opentelemetry import trace
            return trace.get_tracer(name)
        except ImportError:
            pass

    return _NoOpTracer(name)


def add_span_attributes(**attrs) -> None:
    """Add attributes to current span."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span and span.is_recording():
            for k, v in attrs.items():
                span.set_attribute(k, v)
    except Exception:
        pass


class _NoOpSpan:
    """No-op span when OTel not available."""
    def set_attribute(self, key, value): pass
    def set_status(self, status): pass
    def record_exception(self, exc): pass
    def end(self): pass


class _NoOpScope:
    """No-op scope that implements context manager protocol."""
    __slots__ = ('_span',)

    def __init__(self, span: _NoOpSpan):
        self._span = span

    def __enter__(self) -> _NoOpSpan:
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class _NoOpTracer:
    """No-op tracer when OTel not available.

    Returns _NoOpScope context manager compatible with OTel API.
    """
    __slots__ = ('_name',)

    def __init__(self, name: str = "no-op"):
        self._name = name

    def start_as_current_span(
        self,
        name: str,
        context=None,
        links=None,
        start_options=None,
        end_on_exit=True,
    ):
        return _NoOpScope(_NoOpSpan())


# ── Tracing context helpers ────────────────────────────────────────────────────

def get_current_trace_id() -> str:
    """Get current trace ID from span, or empty string."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx:
                return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return ""


def get_current_span_id() -> str:
    """Get current span ID from span, or empty string."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx:
                return format(ctx.span_id, "016x")
    except Exception:
        pass
    return ""