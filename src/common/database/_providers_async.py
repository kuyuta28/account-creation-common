"""
database/_providers_async.py — Async provider operations in mail schema.

Provides async CRUD for mail_providers and provider_domain_tags tables
in the mail schema (mail-service owns these).
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Provider Operations ────────────────────────────────────────────────────────

async def get_providers_async(
    session: AsyncSession,
    service_tag: str | None = None,
) -> list[dict[str, Any]]:
    """Get active mail providers, optionally filtered by service tag."""
    if service_tag:
        query = text("""
            SELECT DISTINCT mp.* FROM mail.mail_providers mp
            LEFT JOIN mail.provider_domain_tags pdt
                ON mp.provider_type = pdt.provider_type
            WHERE mp.disabled = false
                AND pdt.tag = :tag
            ORDER BY mp.last_used ASC NULLS FIRST
        """)
        result = await session.execute(query, {"tag": service_tag})
    else:
        query = text("""
            SELECT * FROM mail.mail_providers
            WHERE disabled = false
            ORDER BY last_used ASC NULLS FIRST
        """)
        result = await session.execute(query)

    return [_row_to_dict(row) for row in result.fetchall()]


async def upsert_provider_async(
    session: AsyncSession,
    provider_type: str,
    api_key: str = "",
    server_id: str = "",
    label: str = "",
) -> int:
    """Insert or update mail provider in mail schema."""
    now = _now()

    # Check existing
    result = await session.execute(
        text("""
            SELECT id FROM mail.mail_providers
            WHERE provider_type = :pt AND api_key = :ak AND server_id = :sid
        """),
        {"pt": provider_type, "ak": api_key, "sid": server_id}
    )
    existing = result.scalar_one_or_none()

    if existing:
        await session.execute(
            text("""
                UPDATE mail.mail_providers
                SET label = :label, updated_at = :now
                WHERE id = :id
            """),
            {"label": label, "now": now, "id": existing}
        )
        return existing

    result = await session.execute(
        text("""
            INSERT INTO mail.mail_providers
            (provider_type, api_key, server_id, label, disabled, fail_count,
             cooldown_until, last_used, created_at, updated_at)
            VALUES (:pt, :ak, :sid, :label, false, 0, '', '', :now, :now)
            RETURNING id
        """),
        {"pt": provider_type, "ak": api_key, "sid": server_id, "label": label, "now": now}
    )
    return result.scalar_one()


async def update_provider_async(
    session: AsyncSession,
    provider_id: int,
    **fields: Any,
) -> bool:
    """Update provider fields."""
    if not fields:
        return True

    set_clauses = []
    params = {"id": provider_id}
    for key, value in fields.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value

    set_clauses.append("updated_at = :now")
    params["now"] = _now()

    await session.execute(
        text(f"UPDATE mail.mail_providers SET {', '.join(set_clauses)} WHERE id = :id"),
        params
    )
    return True


# ── Domain Tag Operations ──────────────────────────────────────────────────────

async def get_domain_tags_async(
    session: AsyncSession,
    provider_type: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    """Get domain tags, optionally filtered."""
    if provider_type and tag:
        query = text("""
            SELECT * FROM mail.provider_domain_tags
            WHERE provider_type = :pt AND tag = :tag
        """)
        result = await session.execute(query, {"pt": provider_type, "tag": tag})
    elif provider_type:
        query = text("SELECT * FROM mail.provider_domain_tags WHERE provider_type = :pt")
        result = await session.execute(query, {"pt": provider_type})
    elif tag:
        query = text("SELECT * FROM mail.provider_domain_tags WHERE tag = :tag")
        result = await session.execute(query, {"tag": tag})
    else:
        result = await session.execute(text("SELECT * FROM mail.provider_domain_tags"))

    return [_tag_row_to_dict(row) for row in result.fetchall()]


async def upsert_domain_tag_async(
    session: AsyncSession,
    provider_type: str,
    tag: str,
) -> int:
    """Insert or get domain tag."""
    result = await session.execute(
        text("""
            INSERT INTO mail.provider_domain_tags (provider_type, tag)
            VALUES (:pt, :tag)
            ON CONFLICT (provider_type, tag) DO UPDATE SET provider_type = EXCLUDED.provider_type
            RETURNING id
        """),
        {"pt": provider_type, "tag": tag}
    )
    return result.scalar_one()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict[str, Any]:
    conn = _connection_str(row["provider_type"], row["api_key"], row["server_id"])
    return {
        "id": row["id"],
        "provider_type": row["provider_type"],
        "api_key": row["api_key"],
        "server_id": row["server_id"],
        "connection_str": conn,
        "label": row["label"],
        "disabled": row["disabled"],
        "fail_count": row["fail_count"],
        "cooldown_until": row["cooldown_until"],
        "last_used": row["last_used"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _tag_row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "provider_type": row["provider_type"],
        "tag": row["tag"],
    }


def _connection_str(provider_type: str, api_key: str, server_id: str) -> str:
    match provider_type:
        case "testmail.app":
            return f"testmail.app:{server_id}:{api_key}"
        case "mailosaur.com":
            return f"mailosaur.com:{api_key}:{server_id}"
        case "guerrillamail.com":
            return "guerrillamail.com"
        case "mail.tm":
            return server_id or "https://api.mail.tm"
        case "gmail.com":
            return f"gmail.com:{api_key}"
        case _:
            raise ValueError(f"Unknown provider_type: {provider_type!r}")