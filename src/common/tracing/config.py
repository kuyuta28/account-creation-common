"""
config.py — Tracing configuration from environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TracingConfig:
    """OpenTelemetry tracing configuration."""
    service_name: str
    enabled: bool = True
    exporter: str = "console"  # "console" | "otlp"
    otlp_endpoint: str = "http://localhost:4317"
    sampler: str = "parentbased_traceidratio"
    sampler_arg: float = 1.0  # 100% in dev, 10% in prod


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def load_tracing_config() -> TracingConfig:
    """Load tracing config from environment variables."""
    service_name = os.getenv("OTEL_SERVICE_NAME", "unknown-service")
    enabled = os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "true"
    exporter = os.getenv("OTEL_EXPORTER_TYPE", "console")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    sampler = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio")
    sampler_arg = _env_int("OTEL_TRACES_SAMPLER_ARG", 100) / 100.0

    return TracingConfig(
        service_name=service_name,
        enabled=enabled,
        exporter=exporter,
        otlp_endpoint=otlp_endpoint,
        sampler=sampler,
        sampler_arg=sampler_arg,
    )
