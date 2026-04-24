"""
database/_async.py — Async database operations using SQLAlchemy Async.

Provides async CRUD helpers that mirror the sync versions in _accounts.py
and _providers.py, but return/use SQLAlchemy AsyncSession.

Usage:
    from common.database._async import insert_account_async

    async with get_async_session() as session:
        await insert_account_async(session, record)
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, TYPE_CHECKING

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from common.src.common.database._engine import _Account, _MailProvider


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Account Operations ─────────────────────────────────────────────────────────

async def insert_account_async(
    session: AsyncSession,
    record,
    ext_data: dict[str, Any] | None = None,
) -> bool:
    """Insert account + extension in a single transaction."""
    from common.database._engine import _Account, _AccountGmail, _AccountAA
    from common.database._engine import _AccountOpenRouter, _AccountElevenLabs
    from common.database._engine import _AccountOllama, _AccountTestmail, _AccountMailosaur

    # Check if account already exists
    existing = await session.execute(
        select(_Account).where(
            _Account.service == record.service.upper(),
            _Account.email == record.email,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    now = _now()
    base = _Account(
        service=record.service.upper(),
        email=record.email,
        password=getattr(record, "password", ""),
        disabled=getattr(record, "disabled", False),
        session_state=getattr(record, "session_state", ""),
        source_email=getattr(record, "source_email", ""),
        check_status=getattr(record, "check_status", ""),
        last_checked=getattr(record, "last_checked", ""),
        last_error=getattr(record, "last_error", ""),
        created_at=record.created_at,
        updated_at=now,
    )
    session.add(base)
    await session.flush()  # get base.id

    svc = record.service.upper()
    ext_row: Any | None = None

    if svc == "GMAIL" and ext_data:
        ext_row = _AccountGmail(
            account_id=base.id,
            totp_secret=ext_data.get("totp_secret", ""),
            app_password=ext_data.get("app_password", ""),
            label=ext_data.get("label", ""),
        )
    elif svc == "ARTIFICIALANALYSIS" and ext_data:
        ext_row = _AccountAA(
            account_id=base.id,
            api_key=ext_data.get("api_key", ""),
            org_slug=ext_data.get("org_slug", ""),
        )
    elif svc == "OPENROUTER" and ext_data:
        ext_row = _AccountOpenRouter(
            account_id=base.id,
            api_key=ext_data.get("api_key", ""),
            credits=ext_data.get("credits", 0),
            quota_pct=str(ext_data.get("quota_pct", "")),
            refresh_token=ext_data.get("refresh_token", ""),
            access_token=ext_data.get("access_token", ""),
            id_token=ext_data.get("id_token", ""),
            token_type=ext_data.get("token_type", ""),
            expired=ext_data.get("expired", ""),
            last_refresh=ext_data.get("last_refresh", ""),
        )
    elif svc == "ELEVENLABS" and ext_data:
        ext_row = _AccountElevenLabs(account_id=base.id, api_key=ext_data.get("api_key", ""))
    elif svc == "OLLAMA" and ext_data:
        ext_row = _AccountOllama(account_id=base.id, api_key=ext_data.get("api_key", ""))
    elif svc == "TESTMAIL" and ext_data:
        ext_row = _AccountTestmail(account_id=base.id, api_key=ext_data.get("api_key", ""))
    elif svc == "MAILOSAUR" and ext_data:
        ext_row = _AccountMailosaur(
            account_id=base.id,
            api_key=ext_data.get("api_key", ""),
            server_id=ext_data.get("server_id", ""),
        )

    if ext_row is not None:
        session.add(ext_row)

    await session.commit()
    return True


async def get_account_by_email_async(
    session: AsyncSession,
    service: str,
    email: str,
) -> dict[str, Any] | None:
    """Async version of get_account_by_email."""
    from common.database._engine import _Account, _AccountGmail, _AccountAA
    from common.database._engine import _AccountOpenRouter, _AccountElevenLabs
    from common.database._engine import _AccountOllama, _AccountTestmail, _AccountMailosaur
    from common.database._engine import _EXTENSION_MODELS

    result = await session.execute(
        select(_Account).where(
            _Account.service == service.upper(),
            _Account.email == email,
        )
    )
    row: _Account | None = result.scalar_one_or_none()
    if row is None:
        return None

    ext_row = None
    ext_model = _EXTENSION_MODELS.get(service.upper())
    if ext_model is not None:
        ext_result = await session.execute(
            select(ext_model).where(ext_model.account_id == row.id)
        )
        ext_row = ext_result.scalar_one_or_none()

    return _to_dict(row, ext_row)


async def update_account_async(
    session: AsyncSession,
    service: str,
    email: str,
    fields: dict[str, Any],
) -> int:
    """Async version of update_account - updates base + extension fields."""
    from common.database._engine import _Account, _AccountGmail, _AccountAA
    from common.database._engine import _AccountOpenRouter, _AccountElevenLabs
    from common.database._engine import _AccountOllama, _AccountTestmail, _AccountMailosaur
    from common.database._engine import _EXT_UPDATABLE, _EXT_FIELD_ALIAS, _EXTENSION_MODELS

    # Find account
    result = await session.execute(
        select(_Account).where(
            _Account.service == service.upper(),
            _Account.email == email,
        )
    )
    row: _Account | None = result.scalar_one_or_none()
    if row is None:
        return 0

    svc = service.upper()
    now = _now()
    base_updates: dict[str, Any] = {}
    ext_updates: dict[str, Any] = {}

    for key, value in fields.items():
        if key in _EXT_UPDATABLE:
            # Map aliases
            mapped = _EXT_FIELD_ALIAS.get(svc, {}).get(key, key)
            if mapped in ("api_key", "totp_secret", "app_password", "label",
                          "org_slug", "server_id"):
                ext_updates[mapped] = value
            elif key in ("credits",):
                ext_updates[key] = value
            else:
                ext_updates[key] = value
        elif key in ("password", "disabled", "session_state", "source_email",
                     "check_status", "last_checked", "last_error", "updated_at"):
            base_updates[key] = value

    # Always update updated_at for base
    base_updates["updated_at"] = now

    if base_updates:
        await session.execute(
            update(_Account)
            .where(_Account.id == row.id)
            .values(**base_updates)
        )

    if ext_updates and svc in _EXTENSION_MODELS:
        ext_model = _EXTENSION_MODELS[svc]
        await session.execute(
            update(ext_model)
            .where(ext_model.account_id == row.id)
            .values(**ext_updates)
        )

    await session.commit()
    return 1


# ── Helper to convert ORM row to dict ────────────────────────────────────────

def _to_dict(row: "_Account", ext=None) -> dict[str, Any]:
    """Convert _Account ORM row to dict (mirrors _engine._to_dict)."""
    from common.database._engine import _compute_status, _parse_quota_pct

    d: dict[str, Any] = {
        "id": row.id,
        "service": row.service,
        "email": row.email,
        "password": row.password,
        "disabled": row.disabled,
        "status": _compute_status(row.disabled, row.check_status),
        "session_state": row.session_state,
        "source_email": row.source_email,
        "check_status": row.check_status,
        "last_checked": row.last_checked,
        "last_error": row.last_error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "api_key": "",
        "credits": 0,
        "quota_pct": None,
        "refresh_token": "",
        "access_token": "",
        "id_token": "",
        "token_type": "",
        "expired": "",
        "last_refresh": "",
        "account_id": "",
        "totp_secret": "",
        "app_password": "",
        "label": "",
    }
    if ext is None:
        return d

    svc = row.service
    if svc == "GMAIL":
        d["totp_secret"] = ext.totp_secret
        d["app_password"] = ext.app_password
        d["label"] = ext.label
    elif svc == "ARTIFICIALANALYSIS":
        d["api_key"] = ext.api_key
        d["account_id"] = ext.org_slug
    elif svc == "OPENROUTER":
        d["api_key"] = ext.api_key
        d["credits"] = ext.credits
        d["quota_pct"] = _parse_quota_pct(ext.quota_pct)
        d["refresh_token"] = ext.refresh_token
        d["access_token"] = ext.access_token
        d["id_token"] = ext.id_token
        d["token_type"] = ext.token_type
        d["expired"] = ext.expired
        d["last_refresh"] = ext.last_refresh
    elif svc in ("ELEVENLABS", "OLLAMA", "TESTMAIL"):
        d["api_key"] = ext.api_key
    elif svc == "MAILOSAUR":
        d["api_key"] = ext.api_key
        d["account_id"] = ext.server_id
    return d


# ── Mailbox Async CRUD ─────────────────────────────────────────────────────────

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
    """Async version of upsert_mailbox_record - for Gmail mailboxes in public schema."""
    from common.database._engine import _Account, _AccountGmail

    canonical = email.strip().lower()
    now = _now()

    # Upsert base
    await session.execute(
        update(_Account)
        .where(_Account.service == "GMAIL", _Account.email == canonical)
        .values(
            password=password,
            source_email=source_email,
            disabled=disabled,
            updated_at=now,
        )
    )
    result = await session.execute(
        select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
    )
    row = result.scalar_one_or_none()

    if row is None:
        from sqlalchemy import insert
        await session.execute(
            insert(_Account).values(
                service="GMAIL",
                email=canonical,
                password=password,
                source_email=source_email,
                disabled=disabled,
                created_at=now,
                updated_at=now,
            )
        )
        result = await session.execute(
            select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
        )
        row = result.scalar_one()

    # Upsert Gmail extension
    await session.execute(
        update(_AccountGmail)
        .where(_AccountGmail.account_id == row.id)
        .values(totp_secret=totp_secret, app_password=app_password, label=label)
    )
    result_ext = await session.execute(
        select(_AccountGmail).where(_AccountGmail.account_id == row.id)
    )
    ext = result_ext.scalar_one_or_none()
    if ext is None:
        from sqlalchemy import insert
        await session.execute(
            insert(_AccountGmail).values(
                account_id=row.id,
                totp_secret=totp_secret,
                app_password=app_password,
                label=label,
            )
        )

    await session.commit()
    return _to_mailbox_dict(row, ext)


def _to_mailbox_dict(row: "_Account", ext=None) -> dict[str, Any]:
    """Convert mailbox row to dict."""
    from common.database._engine import _AccountGmail
    from common.database._engine import _compute_status

    d: dict[str, Any] = {
        "id": row.id,
        "email": row.email,
        "password": row.password,
        "source_email": row.source_email,
        "disabled": row.disabled,
        "status": _compute_status(row.disabled, row.check_status),
        "session_state": row.session_state,
        "check_status": row.check_status,
        "last_checked": row.last_checked,
        "last_error": row.last_error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "totp_secret": "",
        "app_password": "",
        "label": "",
    }
    if ext is not None:
        d["totp_secret"] = ext.totp_secret
        d["app_password"] = ext.app_password
        d["label"] = ext.label
    return d


# ── SMS Phone Async CRUD ───────────────────────────────────────────────────────

async def upsert_sms_phone_async(
    session: AsyncSession,
    phone: str,
    label: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    """Async version of upsert_sms_phone - for SMS phones in public schema."""
    from common.database._engine import _Account

    normalized = phone.strip().replace(" ", "").replace("-", "")
    now = _now()

    await session.execute(
        update(_Account)
        .where(_Account.service == "SMS", _Account.email == normalized)
        .values(source_email=label, disabled=disabled, updated_at=now)
    )
    result = await session.execute(
        select(_Account).where(_Account.service == "SMS", _Account.email == normalized)
    )
    row = result.scalar_one_or_none()

    if row is None:
        from sqlalchemy import insert
        await session.execute(
            insert(_Account).values(
                service="SMS",
                email=normalized,
                source_email=label,
                disabled=disabled,
                created_at=now,
                updated_at=now,
            )
        )
        result = await session.execute(
            select(_Account).where(_Account.service == "SMS", _Account.email == normalized)
        )
        row = result.scalar_one()

    await session.commit()
    return _to_sms_phone_dict(row)


def _to_sms_phone_dict(row: "_Account") -> dict[str, Any]:
    return {
        "phone": row.email,
        "label": row.source_email or "",
        "disabled": row.disabled,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# ── Delete Async CRUD ─────────────────────────────────────────────────────────

async def delete_account_async(session: AsyncSession, service: str, email: str) -> bool:
    """Async version of delete_account."""
    from common.database._engine import _Account
    result = await session.execute(
        delete(_Account).where(
            _Account.service == service.upper(),
            _Account.email == email,
        )
    )
    await session.commit()
    return result.rowcount > 0


async def delete_accounts_async(session: AsyncSession, service: str, emails: set[str]) -> int:
    """Async version of delete_accounts."""
    if not emails:
        return 0
    from common.database._engine import _Account
    result = await session.execute(
        delete(_Account).where(
            _Account.service == service.upper(),
            _Account.email.in_(emails),
        )
    )
    await session.commit()
    return result.rowcount


async def delete_disabled_accounts_async(session: AsyncSession, service: str | None = None) -> int:
    """Async version of delete_disabled_service_accounts."""
    from common.database._engine import _Account
    from sqlalchemy import or_
    disabled_cond = or_(
        _Account.disabled == True,  # noqa: E712
        _Account.check_status.in_(["invalid", "error"]),
    )
    if service is None or service.upper() == "ALL":
        stmt = delete(_Account).where(disabled_cond)
    else:
        stmt = delete(_Account).where(
            _Account.service == service.upper(),
            disabled_cond,
        )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


# ── Service Async CRUD ─────────────────────────────────────────────────────────

async def add_service_async(session: AsyncSession, name: str, has_registrar: bool = False) -> bool:
    """Async version of add_service."""
    from common.database._engine import _Service
    from sqlalchemy import insert, select
    existing = await session.execute(select(_Service).where(_Service.name == name.upper()))
    if existing.scalar_one_or_none() is not None:
        return False
    await session.execute(insert(_Service).values(name=name.upper(), has_registrar=has_registrar))
    await session.commit()
    return True


async def delete_service_async(session: AsyncSession, name: str) -> bool:
    """Async version of delete_service."""
    from common.database._engine import _Service
    from sqlalchemy import delete, select
    result = await session.execute(delete(_Service).where(_Service.name == name.upper()))
    await session.commit()
    return result.rowcount > 0


async def list_services_async(session: AsyncSession) -> list[str]:
    """List all service names."""
    from common.database._engine import _Service
    from sqlalchemy import select
    result = await session.execute(select(_Service.name).order_by(_Service.name))
    return [r[0] for r in result.fetchall() if r[0] != "GMAIL"]


async def service_exists_async(session: AsyncSession, name: str) -> bool:
    """Check if service exists."""
    from common.database._engine import _Service
    from sqlalchemy import select
    result = await session.execute(select(_Service).where(_Service.name == name.upper()))
    return result.scalar_one_or_none() is not None


async def get_accounts_async(
    session: AsyncSession,
    service: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    exclude_service: str | None = None,
) -> list[dict[str, Any]]:
    """Async version of get_accounts - returns list of account dicts.

    Args:
        session: AsyncSession
        service: filter by service name, or None for all
        limit: max rows to return (None = no limit)
        offset: rows to skip (None = 0)
        exclude_service: exclude rows with this service name (e.g. "GMAIL")
    """
    from common.database._engine import _Account
    from sqlalchemy import select, and_
    conditions = []
    if service:
        conditions.append(_Account.service == service.upper())
    if exclude_service:
        conditions.append(_Account.service != exclude_service.upper())
    stmt = select(_Account)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(_Account.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_to_dict(r) for r in rows]


async def count_accounts_async(
    session: AsyncSession,
    service: str | None = None,
    exclude_service: str | None = None,
) -> int:
    """Count total accounts, optionally filtered by service and/or exclude_service."""
    from common.database._engine import _Account
    from sqlalchemy import func, select, and_
    conditions = []
    if service:
        conditions.append(_Account.service == service.upper())
    if exclude_service:
        conditions.append(_Account.service != exclude_service.upper())
    stmt = select(func.count(_Account.id))
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await session.execute(stmt)
    return result.scalar() or 0
