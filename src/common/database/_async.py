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

from sqlalchemy import case, func, select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    include_disabled: bool = True,
) -> list[dict[str, Any]]:
    """Async version of get_accounts - returns list of account dicts."""
    from common.database._engine import _Account, _EXTENSION_MODELS
    from sqlalchemy import select, and_
    conditions = []
    if service:
        conditions.append(_Account.service == service.upper())
    if exclude_service:
        conditions.append(_Account.service != exclude_service.upper())
    if not include_disabled:
        conditions.append(_Account.disabled == False)  # noqa: E712
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
    if not rows:
        return []

    ext_by_account_id: dict[int, Any] = {}
    service_names = {row.service for row in rows}
    for service_name in service_names:
        ext_model = _EXTENSION_MODELS.get(service_name)
        if ext_model is None:
            continue
        account_ids = [row.id for row in rows if row.service == service_name]
        ext_rows = (await session.execute(
            select(ext_model).where(ext_model.account_id.in_(account_ids))
        )).scalars().all()
        ext_by_account_id.update({ext.account_id: ext for ext in ext_rows})

    return [_to_dict(row, ext_by_account_id.get(row.id)) for row in rows]


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


async def count_accounts_by_service_async(
    session: AsyncSession,
    exclude_service: str | None = None,
) -> dict[str, int]:
    from common.database._engine import _Account
    from sqlalchemy import func, select

    stmt = select(_Account.service, func.count(_Account.id)).group_by(_Account.service).order_by(_Account.service)
    if exclude_service:
        stmt = stmt.where(_Account.service != exclude_service.upper())
    result = await session.execute(stmt)
    return {service: count for service, count in result.fetchall()}


async def get_mailboxes_async(session: AsyncSession) -> list[dict[str, Any]]:
    from common.database._engine import _Account, _AccountGmail, _to_mailbox_dict

    rows = (await session.execute(
        select(_Account).where(_Account.service == "GMAIL").order_by(_Account.email)
    )).scalars().all()
    if not rows:
        return []
    ids = [row.id for row in rows]
    ext_rows = (await session.execute(
        select(_AccountGmail).where(_AccountGmail.account_id.in_(ids))
    )).scalars().all()
    ext_map = {ext.account_id: ext for ext in ext_rows}
    return [_to_mailbox_dict(row, ext_map.get(row.id)) for row in rows]


async def get_mailbox_record_async(session: AsyncSession, email: str) -> dict[str, Any] | None:
    from common.database._engine import _Account, _AccountGmail, _to_mailbox_dict

    canonical = email.strip().lower()
    row = (await session.execute(
        select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
    )).scalar_one_or_none()
    if row is None:
        return None
    ext = (await session.execute(
        select(_AccountGmail).where(_AccountGmail.account_id == row.id)
    )).scalar_one_or_none()
    return _to_mailbox_dict(row, ext)


async def upsert_mailbox_record_async(
    session: AsyncSession,
    email: str,
    app_password: str = "",
    totp_secret: str = "",
    password: str = "",
    source_email: str = "",
    label: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    from common.database._engine import _Account, _AccountGmail, _Service

    canonical = email.strip().lower()
    now = _now()
    await session.execute(
        pg_insert(_Service)
        .values(name="GMAIL", has_registrar=False)
        .on_conflict_do_nothing(index_elements=["name"])
    )
    await session.execute(
        pg_insert(_Account)
        .values(
            service="GMAIL",
            email=canonical,
            password=password,
            source_email=source_email,
            disabled=disabled,
            session_state="",
            check_status="",
            last_checked="",
            last_error="",
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["service", "email"],
            set_={"password": password, "source_email": source_email, "disabled": disabled, "updated_at": now},
        )
    )
    row = (await session.execute(
        select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
    )).scalar_one()
    await session.execute(
        pg_insert(_AccountGmail)
        .values(account_id=row.id, totp_secret=totp_secret, app_password=app_password, label=label)
        .on_conflict_do_update(
            index_elements=["account_id"],
            set_={"totp_secret": totp_secret, "app_password": app_password, "label": label},
        )
    )
    await session.commit()
    return await get_mailbox_record_async(session, canonical) or {}


async def delete_mailbox_record_async(session: AsyncSession, email: str) -> bool:
    from common.database._engine import _Account

    canonical = email.strip().lower()
    result = await session.execute(delete(_Account).where(_Account.service == "GMAIL", _Account.email == canonical))
    await session.commit()
    return result.rowcount > 0


async def save_mailbox_google_auth_state_async(session: AsyncSession, email: str, auth_state_json: str) -> bool:
    from common.database._engine import _Account

    canonical = email.strip().lower()
    result = await session.execute(
        update(_Account)
        .where(_Account.service == "GMAIL", _Account.email == canonical)
        .values(session_state=auth_state_json, updated_at=_now())
    )
    await session.commit()
    return result.rowcount > 0


async def block_mailbox_for_service_async(session: AsyncSession, email: str, service: str, reason: str = "") -> None:
    from common.database._engine import _MailboxServiceBlock

    await session.execute(
        pg_insert(_MailboxServiceBlock)
        .values(email=email.strip().lower(), service=service.upper(), reason=reason, blocked_at=_now())
        .on_conflict_do_update(
            index_elements=["email", "service"],
            set_={"reason": reason, "blocked_at": _now()},
        )
    )
    await session.commit()


async def unblock_mailbox_for_service_async(session: AsyncSession, email: str, service: str) -> bool:
    from common.database._engine import _MailboxServiceBlock

    result = await session.execute(delete(_MailboxServiceBlock).where(
        _MailboxServiceBlock.email == email.strip().lower(),
        _MailboxServiceBlock.service == service.upper(),
    ))
    await session.commit()
    return result.rowcount > 0


async def get_available_mailboxes_for_service_async(session: AsyncSession, service: str) -> list[dict[str, Any]]:
    from common.database._engine import _Account, _AccountGmail, _MailboxServiceBlock, _to_mailbox_dict

    blocked_emails = select(_MailboxServiceBlock.email).where(_MailboxServiceBlock.service == service.upper())
    rows = (await session.execute(
        select(_Account)
        .where(_Account.service == "GMAIL")
        .where(_Account.disabled == False)  # noqa: E712
        .where(_Account.email.not_in(blocked_emails))
        .order_by(_Account.email)
    )).scalars().all()
    if not rows:
        return []
    ids = [row.id for row in rows]
    ext_rows = (await session.execute(
        select(_AccountGmail).where(_AccountGmail.account_id.in_(ids))
    )).scalars().all()
    ext_map = {ext.account_id: ext for ext in ext_rows}
    return [_to_mailbox_dict(row, ext_map.get(row.id)) for row in rows]


async def get_service_blocks_async(session: AsyncSession, service: str | None = None) -> list[dict[str, Any]]:
    from common.database._engine import _MailboxServiceBlock

    stmt = select(_MailboxServiceBlock)
    if service is not None:
        stmt = stmt.where(_MailboxServiceBlock.service == service.upper())
    rows = (await session.execute(
        stmt.order_by(_MailboxServiceBlock.service, _MailboxServiceBlock.email)
    )).scalars().all()
    return [{"email": row.email, "service": row.service, "reason": row.reason, "blocked_at": row.blocked_at} for row in rows]


async def get_sms_phones_async(session: AsyncSession) -> list[dict[str, Any]]:
    from common.database._engine import _Account

    rows = (await session.execute(
        select(_Account).where(_Account.service == "SMS").order_by(_Account.email)
    )).scalars().all()
    return [_to_sms_phone_dict(row) for row in rows]


async def delete_sms_phone_async(session: AsyncSession, phone: str) -> bool:
    from common.database._engine import _Account

    normalized = phone.strip().replace(" ", "").replace("-", "")
    result = await session.execute(delete(_Account).where(_Account.service == "SMS", _Account.email == normalized))
    await session.commit()
    return result.rowcount > 0


async def get_used_gmail_variations_async(
    session: AsyncSession,
    source_email: str,
    service: str | None = None,
) -> list[dict[str, Any]]:
    from sqlalchemy import or_
    from common.database._engine import _Account

    canonical = source_email.lower().strip()
    stmt = select(_Account).where(or_(_Account.email == canonical, _Account.source_email == canonical))
    if service:
        stmt = stmt.where(_Account.service == service.upper())
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_dict(row) for row in rows]


async def check_gmail_variations_availability_async(
    session: AsyncSession,
    variations: list[str],
    service: str,
) -> dict[str, bool]:
    from common.database._engine import _Account

    lower_vars = [variation.lower() for variation in variations]
    existing = set((await session.execute(
        select(_Account.email).where(_Account.service == service.upper(), _Account.email.in_(lower_vars))
    )).scalars().all())
    return {variation: variation not in existing for variation in lower_vars}


async def upsert_mail_provider_async(
    session: AsyncSession,
    provider_type: str,
    api_key: str = "",
    server_id: str = "",
    label: str = "",
) -> int:
    from common.database._engine import _MailProvider

    now = _now()
    stmt = (
        pg_insert(_MailProvider)
        .values(
            provider_type=provider_type,
            api_key=api_key,
            server_id=server_id,
            label=label,
            disabled=False,
            fail_count=0,
            cooldown_until="",
            last_used="",
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["provider_type", "api_key", "server_id"],
            set_={"label": label, "updated_at": now, "disabled": False},
        )
        .returning(_MailProvider.id)
    )
    provider_id = await session.scalar(stmt)
    await session.commit()
    return int(provider_id)


async def get_mail_providers_async(
    session: AsyncSession,
    service_tag: str | None = None,
) -> list[dict[str, Any]]:
    import base64
    import json as json_lib
    from sqlalchemy import exists
    from common.database._engine import _Account, _AccountGmail, _MailProvider, _MailboxServiceBlock, _ProviderDomainTag, _to_provider_dict

    svc_tag = service_tag.lower() if service_tag else None
    stmt = select(_MailProvider).where(_MailProvider.disabled.is_(False))
    if svc_tag:
        has_tag = exists().where(
            _ProviderDomainTag.provider_type == _MailProvider.provider_type,
            _ProviderDomainTag.tag == svc_tag,
        )
        stmt = stmt.where(has_tag)
    providers = (await session.execute(stmt)).scalars().all()
    result = [_to_provider_dict(provider) for provider in providers]

    gmail_tagged = True
    if svc_tag:
        gmail_tagged = (await session.scalar(
            select(func.count()).where(
                _ProviderDomainTag.provider_type == "gmail.com",
                _ProviderDomainTag.tag == svc_tag,
            )
        ) or 0) > 0

    if gmail_tagged:
        already_used_in_service = select(_Account.email).where(_Account.service == svc_tag.upper()) if svc_tag else None
        stmt_gmail = select(_Account).where(_Account.service == "GMAIL", _Account.disabled.is_(False)).order_by(_Account.email)
        if already_used_in_service is not None:
            stmt_gmail = stmt_gmail.where(_Account.email.not_in(already_used_in_service))
        if svc_tag:
            blocked_emails = select(_MailboxServiceBlock.email).where(_MailboxServiceBlock.service == svc_tag.upper())
            stmt_gmail = stmt_gmail.where(_Account.email.not_in(blocked_emails))
        gmail_rows = (await session.execute(stmt_gmail)).scalars().all()
        gmail_exts = {}
        if gmail_rows:
            gmail_ids = [row.id for row in gmail_rows]
            gmail_ext_rows = (await session.execute(
                select(_AccountGmail).where(_AccountGmail.account_id.in_(gmail_ids))
            )).scalars().all()
            gmail_exts = {ext.account_id: ext for ext in gmail_ext_rows}
        result.extend({
            "id": None,
            "provider_type": "gmail.com",
            "api_key": row.email,
            "server_id": "",
            "connection_str": "gmail.com:{email}:{meta}".format(
                email=row.email,
                meta=base64.urlsafe_b64encode(json_lib.dumps(
                    {
                        "s": row.session_state,
                        "p": row.password,
                        "t": gmail_exts[row.id].totp_secret if row.id in gmail_exts else "",
                    },
                    separators=(",", ":"),
                ).encode()).decode(),
            ),
            "label": row.email,
            "disabled": False,
            "fail_count": 0,
            "cooldown_until": "",
            "last_used": "",
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        } for row in gmail_rows)
    return result


async def get_all_providers_with_tags_async(session: AsyncSession) -> list[dict[str, Any]]:
    from common.database._engine import _MailProvider, _ProviderDomainTag, _to_provider_dict

    providers = (await session.execute(select(_MailProvider))).scalars().all()
    if not providers:
        return []

    provider_types = {p.provider_type for p in providers}
    tag_rows = (await session.execute(
        select(_ProviderDomainTag.provider_type, _ProviderDomainTag.tag).where(
            _ProviderDomainTag.provider_type.in_(provider_types)
        )
    )).all()
    type_tags: dict[str, list[str]] = {provider_type: [] for provider_type in provider_types}
    for provider_type, tag in tag_rows:
        type_tags[provider_type].append(tag)

    result = []
    for provider in providers:
        item = _to_provider_dict(provider)
        item["tags"] = sorted(type_tags.get(provider.provider_type, []))
        result.append(item)
    return result


async def update_provider_async(session: AsyncSession, provider_id: int, **fields) -> bool:
    from common.database._engine import _MailProvider

    allowed = {"disabled", "label", "fail_count", "cooldown_until"}
    safe = {key: value for key, value in fields.items() if key in allowed}
    if not safe:
        return False
    safe["updated_at"] = _now()
    result = await session.execute(
        update(_MailProvider).where(_MailProvider.id == provider_id).values(**safe)
    )
    await session.commit()
    return result.rowcount > 0


async def get_provider_domains_async(session: AsyncSession) -> list[dict[str, Any]]:
    from common.database._engine import _Account, _MailProvider, _ProviderDomainTag

    counts = (await session.execute(
        select(
            _MailProvider.provider_type,
            func.count().label("total"),
            func.sum(case((_MailProvider.disabled == False, 1), else_=0)).label("active"),  # noqa: E712
        ).group_by(_MailProvider.provider_type)
    )).all()

    tag_rows = (await session.execute(
        select(_ProviderDomainTag.provider_type, _ProviderDomainTag.tag)
    )).all()
    type_tags: dict[str, list[str]] = {}
    for provider_type, tag in tag_rows:
        type_tags.setdefault(provider_type, []).append(tag)

    result = [
        {
            "domain": row.provider_type,
            "tags": sorted(type_tags.get(row.provider_type, [])),
            "total": row.total,
            "active": row.active or 0,
        }
        for row in sorted(counts, key=lambda r: r.provider_type)
    ]

    gmail_counts = (await session.execute(
        select(
            func.count().label("total"),
            func.sum(case((_Account.disabled == False, 1), else_=0)).label("active"),  # noqa: E712
        ).where(_Account.service == "GMAIL")
    )).one()
    if gmail_counts.total:
        result.append({
            "domain": "gmail.com",
            "tags": sorted(type_tags.get("gmail.com", [])),
            "total": gmail_counts.total,
            "active": gmail_counts.active or 0,
        })
        result.sort(key=lambda r: r["domain"])

    return result


async def set_provider_domain_tags_async(session: AsyncSession, provider_domain: str, tags: list[str]) -> int:
    from common.database._engine import _ProviderDomainTag

    clean = [tag.strip().lower() for tag in tags if tag.strip()]
    await session.execute(delete(_ProviderDomainTag).where(
        _ProviderDomainTag.provider_type == provider_domain
    ))
    for tag in clean:
        await session.execute(
            pg_insert(_ProviderDomainTag)
            .values(provider_type=provider_domain, tag=tag)
            .on_conflict_do_nothing(index_elements=["provider_type", "tag"])
        )
    await session.commit()
    return len(clean)


async def cycle_provider_tag_async(session: AsyncSession, provider_domain: str, service: str) -> list[str]:
    from common.database._engine import _ProviderDomainTag

    current_tags = list((await session.execute(
        select(_ProviderDomainTag.tag).where(
            _ProviderDomainTag.provider_type == provider_domain
        )
    )).scalars().all())

    active_key = service.strip().lower()
    blocked_key = f"{active_key}:blocked"

    if active_key in current_tags:
        await session.execute(delete(_ProviderDomainTag).where(
            _ProviderDomainTag.provider_type == provider_domain,
            _ProviderDomainTag.tag == active_key,
        ))
        await session.execute(
            pg_insert(_ProviderDomainTag)
            .values(provider_type=provider_domain, tag=blocked_key)
            .on_conflict_do_nothing(index_elements=["provider_type", "tag"])
        )
        next_tags = [tag for tag in current_tags if tag != active_key] + [blocked_key]
    elif blocked_key in current_tags:
        await session.execute(delete(_ProviderDomainTag).where(
            _ProviderDomainTag.provider_type == provider_domain,
            _ProviderDomainTag.tag == blocked_key,
        ))
        next_tags = [tag for tag in current_tags if tag != blocked_key]
    else:
        await session.execute(
            pg_insert(_ProviderDomainTag)
            .values(provider_type=provider_domain, tag=active_key)
            .on_conflict_do_nothing(index_elements=["provider_type", "tag"])
        )
        next_tags = [*current_tags, active_key]

    await session.commit()
    return sorted(next_tags)
