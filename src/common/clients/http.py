"""
http.py — Internal HTTP client with automatic request ID and trace propagation.
"""
from __future__ import annotations

from typing import Any

import httpx

from common.logging.context import get_request_id, get_trace_info


class TracingClient(httpx.AsyncClient):
    """httpx AsyncClient that auto-injects X-Request-ID and traceparent headers."""

    def __init__(self, *args, internal_key: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._internal_key = internal_key

    def _inject_headers(self, kwargs: dict) -> None:
        """Inject tracing headers into request kwargs."""
        headers = kwargs.get("headers", {}) or {}
        request_id = get_request_id()
        if request_id:
            headers["X-Request-ID"] = request_id

        trace_info = get_trace_info()
        if trace_info:
            headers["traceparent"] = trace_info.traceparent

        if self._internal_key:
            headers["X-Internal-Key"] = self._internal_key

        kwargs["headers"] = headers

    async def get(self, *args, **kwargs) -> httpx.Response:
        self._inject_headers(kwargs)
        return await super().get(*args, **kwargs)

    async def post(self, *args, **kwargs) -> httpx.Response:
        self._inject_headers(kwargs)
        return await super().post(*args, **kwargs)

    async def put(self, *args, **kwargs) -> httpx.Response:
        self._inject_headers(kwargs)
        return await super().put(*args, **kwargs)

    async def patch(self, *args, **kwargs) -> httpx.Response:
        self._inject_headers(kwargs)
        return await super().patch(*args, **kwargs)

    async def delete(self, *args, **kwargs) -> httpx.Response:
        self._inject_headers(kwargs)
        return await super().delete(*args, **kwargs)


# ── Simple async context manager ──────────────────────────────────────────────

_internal_key: str | None = None


def set_internal_key(key: str) -> None:
    """Set the internal API key for all TracingClient instances."""
    global _internal_key
    _internal_key = key


def get_internal_key() -> str | None:
    return _internal_key


class InternalClient:
    """Async context manager for HTTP calls to internal services."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
        self._client: TracingClient | None = None

    async def __aenter__(self) -> TracingClient:
        self._client = TracingClient(
            base_url=self.base_url,
            timeout=self.timeout,
            internal_key=_internal_key,
        )
        return self._client

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        async with self as client:
            return await client.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        async with self as client:
            return await client.post(url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        async with self as client:
            return await client.put(url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        async with self as client:
            return await client.delete(url, **kwargs)
