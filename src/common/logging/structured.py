"""
structured.py — Structured JSON logging.

JSONFormatter: logging.Formatter subclass that outputs machine-parseable logs.
LogContext: gathers context from contextvars at log time.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, UTC

from .context import get_request_id, get_trace_info


class JSONFormatter(logging.Formatter):
    """Formatter that outputs structured JSON with request/trace context."""

    def __init__(self, service_name: str = "unknown") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        trace_info = get_trace_info()
        request_id = get_request_id()

        log_entry = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if request_id:
            log_entry["request_id"] = request_id

        if trace_info:
            log_entry["trace_id"] = trace_info.trace_id
            log_entry["span_id"] = trace_info.span_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Merge extra fields (from structured_log call)
        if hasattr(record, "_extra_fields"):
            log_entry.update(record._extra_fields)

        return json.dumps(log_entry, ensure_ascii=False)


def structured_log(
    logger: logging.Logger,
    level: int,
    msg: str,
    **kwargs,
) -> None:
    """Log with extra fields merged into JSON output."""
    record = logging.LogRecord(
        name=logger.name,
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    record._extra_fields = kwargs  # type: ignore
    logger.handle(record)


def log_info_structured(logger: logging.Logger, msg: str, **kwargs) -> None:
    structured_log(logger, logging.INFO, msg, **kwargs)


def log_error_structured(logger: logging.Logger, msg: str, **kwargs) -> None:
    structured_log(logger, logging.ERROR, msg, **kwargs)


def log_warning_structured(logger: logging.Logger, msg: str, **kwargs) -> None:
    structured_log(logger, logging.WARNING, msg, **kwargs)


def log_debug_structured(logger: logging.Logger, msg: str, **kwargs) -> None:
    structured_log(logger, logging.DEBUG, msg, **kwargs)
