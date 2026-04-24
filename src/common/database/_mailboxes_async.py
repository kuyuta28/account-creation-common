"""
database/_mailboxes_async.py — Async Gmail mailbox CRUD + service blocks.
Mailboxes are stored as accounts(service='GMAIL') in public schema.
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _to_mailbox_dict(row) -> dict[str, Any]:
    return {
        "email": row["email"],
        "app_password": row.get("app_password", ""),
        "totp_secret": row.get("totp_secret", ""),
        "password": row.get("password", ""),
        "source_email": row.get("source_email", ""),
        "google_auth_state": row.get("session_state", ""),
        "disabled": row.get("disabled", False),
        "label": row.get("label", ""),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
    }


async def delete_sms_phone_async(session: AsyncSession, phone: str) -> bool:
    """Delete SMS phone."""
    normalized = phone.strip().replace(" ", "").replace("-", "")
    result = await session.execute(
        text("DELETE FROM public.accounts WHERE service = 'SMS' AND email = :email"),
        {"email": normalized}
    )
    await session.commit()
    return result.rowcount > 0 if hasattr(result, 'rowcount') else True


async def get_mailbox_record_async(session: AsyncSession, email: str) -> dict[str, Any] | None:
    """Get Gmail mailbox by email."""
    canonical = email.strip().lower()
    result = await session.execute(
        text("""
            SELECT a.*, g.totp_secret, g.app_password, g.label
            FROM public.accounts a
            LEFT JOIN public.accounts_gmail g ON a.id = g.account_id
            WHERE a.service = 'GMAIL' AND LOWER(a.email) = :email
        """),
        {"email": canonical}
    )
    row = result.fetchone()
    return _to_mailbox_dict(row) if row else None


async def upsert_mailbox_async(
    session: AsyncSession,
    email: str,
    app_password: str = "",
    totp_secret: str = "",
    password: str = "",
    source_email: str = "",
    label: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    """Insert or update Gmail mailbox. Returns dict after save."""
    canonical = email.strip().lower()
    now = _now()

    # Upsert base account
    await session.execute(
        text("""
            INSERT INTO public.accounts
            (service, email, password, source_email, disabled, session_state,
             check_status, last_checked, last_error, created_at, updated_at)
            VALUES ('GMAIL', :email, :password, :source_email, :disabled, '',
                    '', '', '', :now, :now)
            ON CONFLICT (service, email) DO UPDATE
            SET password = :password, source_email = :source_email,
                disabled = :disabled, updated_at = :now
        """),
        {
            "email": canonical, "password": password,
            "source_email": source_email, "disabled": disabled, "now": now
        }
    )

    # Get account id
    result = await session.execute(
        text("SELECT id FROM public.accounts WHERE service = 'GMAIL' AND email = :email"),
        {"email": canonical}
    )
    account_id = result.scalar_one()

    # Upsert Gmail extension
    await session.execute(
        text("""
            INSERT INTO public.accounts_gmail (account_id, totp_secret, app_password, label)
            VALUES (:id, :totp, :pwd, :label)
            ON CONFLICT (account_id) DO UPDATE
            SET totp_secret = :totp, app_password = :pwd, label = :label
        """),
        {"id": account_id, "totp": totp_secret, "pwd": app_password, "label": label}
    )

    await session.commit()
    return await get_mailbox_record_async(session, canonical)


async def delete_mailbox_async(session: AsyncSession, email: str) -> bool:
    """Delete Gmail mailbox."""
    canonical = email.strip().lower()
    result = await session.execute(
        text("DELETE FROM public.accounts WHERE service = 'GMAIL' AND email = :email"),
        {"email": canonical}
    )
    await session.commit()
    return result.rowcount > 0 if hasattr(result, 'rowcount') else True


async def get_available_mailboxes_async(session: AsyncSession, service: str) -> list[dict[str, Any]]:
    """Get mailboxes not blocked for service."""
    svc = service.upper()
    result = await session.execute(
        text("""
            SELECT a.*, g.totp_secret, g.app_password, g.label
            FROM public.accounts a
            LEFT JOIN public.accounts_gmail g ON a.id = g.account_id
            WHERE a.service = 'GMAIL'
              AND a.disabled = false
              AND a.email NOT IN (
                  SELECT email FROM public.mailbox_service_blocks WHERE service = :svc
              )
            ORDER BY a.email
        """),
        {"svc": svc}
    )
    return [_to_mailbox_dict(row) for row in result.fetchall()]


async def save_mailbox_google_auth_state_async(
    session: AsyncSession, email: str, auth_state_json: str
) -> bool:
    """Save Playwright storage_state JSON to accounts.session_state."""
    canonical = email.strip().lower()
    now = _now()
    result = await session.execute(
        text("""
            UPDATE public.accounts
            SET session_state = :state, updated_at = :now
            WHERE service = 'GMAIL' AND email = :email
        """),
        {"state": auth_state_json, "now": now, "email": canonical}
    )
    await session.commit()
    return result.rowcount > 0 if hasattr(result, 'rowcount') else True


async def get_mailbox_google_auth_state_async(
    session: AsyncSession, email: str
) -> str | None:
    """Get storage_state for Gmail mailbox."""
    canonical = email.strip().lower()
    result = await session.execute(
        text("SELECT session_state FROM public.accounts WHERE service = 'GMAIL' AND email = :email"),
        {"email": canonical}
    )
    row = result.fetchone()
    if not row:
        return None
    return dict(row).get("session_state")


# ── SMS Phone CRUD ─────────────────────────────────────────────────────────────

def _to_sms_phone_dict(row) -> dict[str, Any]:
    return {
        "phone": row["email"],
        "label": row.get("source_email", ""),
        "disabled": row.get("disabled", False),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
    }


async def get_sms_phones_async(session: AsyncSession) -> list[dict[str, Any]]:
    """Get all SMS phone numbers."""
    result = await session.execute(
        text("SELECT * FROM public.accounts WHERE service = 'SMS' ORDER BY email")
    )
    return [_to_sms_phone_dict(row) for row in result.fetchall()]


async def upsert_sms_phone_async(
    session: AsyncSession,
    phone: str,
    label: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    """Insert or update SMS phone."""
    normalized = phone.strip().replace(" ", "").replace("-", "")
    now = _now()

    await session.execute(
        text("""
            INSERT INTO public.accounts
            (service, email, source_email, disabled, created_at, updated_at,
             password, check_status, last_checked, last_error, session_state)
            VALUES ('SMS', :email, :label, :disabled, :now, :now,
                    '', '', '', '', '')
            ON CONFLICT (service, email) DO UPDATE
            SET source_email = :label, disabled = :disabled, updated_at = :now
        """),
        {"email": normalized, "label": label, "disabled": disabled, "now": now}
    )
    await session.commit()

    result = await session.execute(
        text("SELECT * FROM public.accounts WHERE service = 'SMS' AND email = :email"),
        {"email": normalized}
    )
    row = result.fetchone()
    return _to_sms_phone_dict(row) if row else {}


async def delete_sms_phone_async(session: AsyncSession, phone: str) -> bool:
    """Delete SMS phone."""
    normalized = phone.strip().replace(" ", "").replace("-", "")
    result = await session.execute(
        text("DELETE FROM public.accounts WHERE service = 'SMS' AND email = :email"),
        {"email": normalized}
    )
    await session.commit()
    return result.rowcount > 0 if hasattr(result, 'rowcount') else True
