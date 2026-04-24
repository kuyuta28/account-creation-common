"""
session.py — Generic Playwright session persistence via Registrar Internal API.

Lưu/load Playwright storage_state (cookies + localStorage + sessionStorage)
vào cột session_state trong bảng accounts trên PostgreSQL qua Registrar API.

Public API:
  save_session(service, email, context) -> None
  load_session(service, email) -> dict | None
  has_session(service, email) -> bool
"""
from __future__ import annotations

import json

from .internal_client import InternalClient


async def save_session(service: str, email: str, context) -> None:
    """Lưu Playwright storage_state của context vào Registrar DB qua API.

    Args:
        service:  Service tag (ví dụ: "KLINGAI", "ARTIFICIALANALYSIS").
        email:    Email định danh account.
        context:  Playwright BrowserContext đang active.
    """
    state = await context.storage_state()
    async with InternalClient() as client:
        await client.save_session(service.upper(), email, json.dumps(state, ensure_ascii=False))


async def load_session(service: str, email: str) -> dict | None:
    """Load storage_state từ Registrar DB.

    Returns:
        dict phù hợp cho `browser.new_context(storage_state=...)`.
        None nếu chưa có session được lưu.

    Raises:
        RuntimeError: nếu account không tồn tại.
    """
    async with InternalClient() as client:
        acc = await client.get_account(service.upper(), email)
        if not acc:
            raise RuntimeError(f"Account không tồn tại trong DB: {service}/{email}")
        raw = acc.get("session_state", "")
        if not raw:
            return None
        return json.loads(raw)


async def has_session(service: str, email: str) -> bool:
    """Kiểm tra account có session được lưu chưa."""
    async with InternalClient() as client:
        acc = await client.get_account(service.upper(), email)
        if not acc:
            return False
        return bool(acc.get("session_state", ""))
