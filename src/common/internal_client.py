"""
internal_client.py — Client for Registrar's internal API.

Used by Mail-Service and AA-Proxy to communicate with Registrar.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


_REGISTRAR_URL = os.getenv("REGISTRAR_URL", "http://registrar:8709")
_INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "ccs-internal")
_TIMEOUT = 30.0


def _headers() -> dict[str, str]:
    return {
        "X-Internal-Key": _INTERNAL_KEY,
        "Content-Type": "application/json",
    }


class InternalClient:
    """Client for Registrar internal API."""

    def __init__(self, base_url: str = _REGISTRAR_URL, api_key: str = _INTERNAL_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-Internal-Key": self.api_key},
            timeout=_TIMEOUT,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # ── Account Operations ─────────────────────────────────────────────────────

    async def get_account(self, service: str, email: str) -> dict[str, Any] | None:
        """Get account from Registrar."""
        if not self._client:
            raise RuntimeError("Use 'async with InternalClient()'")
        try:
            resp = await self._client.get(f"/api/v1/internal/accounts/{service}/{email}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()["data"]
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to get account: {e}") from e

    async def list_accounts(self, service: str | None = None) -> list[dict[str, Any]]:
        """List accounts, optionally filtered by service."""
        if not self._client:
            raise RuntimeError("Use 'async with InternalClient()'")
        try:
            params = {"service": service} if service else {}
            resp = await self._client.get("/api/v1/internal/accounts", params=params)
            resp.raise_for_status()
            data = resp.json()["data"] or []
            if isinstance(data, dict):
                return data.get("accounts", [])
            return data
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to list accounts: {e}") from e

    async def upsert_account(
        self,
        service: str,
        email: str,
        api_key: str = "",
        password: str = "",
    ) -> bool:
        """Create or update account on Registrar."""
        if not self._client:
            raise RuntimeError("Use 'async with InternalClient()'")
        try:
            resp = await self._client.post(
                "/api/v1/internal/accounts/upsert",
                json={
                    "service": service,
                    "email": email,
                    "api_key": api_key,
                    "password": password,
                },
            )
            resp.raise_for_status()
            return resp.json()["data"]["created"]
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to upsert account: {e}") from e

    async def update_account(
        self,
        service: str,
        email: str,
        **fields: Any,
    ) -> bool:
        """Update account fields on Registrar."""
        if not self._client:
            raise RuntimeError("Use 'async with InternalClient()'")
        try:
            resp = await self._client.patch(
                f"/api/v1/internal/accounts/{service}/{email}",
                json=fields,
            )
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to update account: {e}") from e

    async def delete_account(self, service: str, email: str) -> bool:
        """Delete account from Registrar."""
        if not self._client:
            raise RuntimeError("Use 'async with InternalClient()'")
        try:
            resp = await self._client.delete(f"/api/v1/internal/accounts/{service}/{email}")
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to delete account: {e}") from e

    async def save_session(self, service: str, email: str, session_state: str) -> bool:
        """Save session_state for an account."""
        if not self._client:
            raise RuntimeError("Use 'async with InternalClient()'")
        try:
            resp = await self._client.put(
                f"/api/v1/internal/accounts/{service}/{email}/session",
                json={"session_state": session_state},
            )
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to save session: {e}") from e

    # ── Health ───────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Check if Registrar is healthy."""
        if not self._client:
            raise RuntimeError("Use 'async with InternalClient()'")
        try:
            resp = await self._client.get("/api/v1/internal/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
