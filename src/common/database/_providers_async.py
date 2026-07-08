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


async def pick_testmail_namespace_async(
    session: AsyncSession,
    service_tag: str | None,
    monthly_quota: int,
) -> dict[str, Any] | None:
    """Atomic pick 1 testmail namespace ít dùng nhất trong tháng, race-safe.

    Source of truth: public.accounts_testmail (1 bảng vừa identity vừa pool).
    Counting round-robin: mỗi namespace có usage_count (số email đã tiêu trong tháng)
    + usage_month (YYYY-MM). Pick namespace có usage_count thấp nhất, skip những cái
    đã near/exceed quota. Lazy reset monthly (sang tháng mới → usage_count về 0).

    Bump usage_count ATOMIC ngay trong UPDATE pick (không đợi email về) → request
    concurrent sau thấy count đã tăng → pick namespace khác. Trước đây chỉ set
    last_used, count vẫn 0 → batch concurrent cùng pick 1 namespace.

    FOR UPDATE SKIP LOCKED → 2 signup concurrent không pick cùng namespace.

    service_tag hiện KHÔNG filter (testmail namespace dùng chung cho mọi service).
    Trả về dict có connection_str (= api_key compound "testmail.app:{ns}:{key}")
    + id (= account_id) hoặc None nếu pool cạn tháng này.
    """
    now = _now()
    cur_month = datetime.now(UTC).strftime("%Y-%m")
    near = max(1, int(monthly_quota * 0.9))

    result = await session.execute(
        text("""
            WITH candidate AS (
                SELECT at.*,
                       CASE WHEN at.usage_month = :cur_month THEN at.usage_count ELSE 0 END AS eff_count
                FROM public.accounts_testmail at
                WHERE at.disabled = false
                  AND (at.cooldown_until = '' OR at.cooldown_until < :now)
                  AND (at.usage_month <> :cur_month OR at.usage_count < :quota)
                ORDER BY eff_count ASC, at.last_used ASC NULLS FIRST, at.account_id ASC
                FOR UPDATE OF at SKIP LOCKED
                LIMIT 1
            )
            UPDATE public.accounts_testmail
            SET usage_count = CASE
                    WHEN public.accounts_testmail.usage_month = :cur_month THEN public.accounts_testmail.usage_count + 1
                    ELSE 1
                  END,
                usage_month = :cur_month,
                cooldown_until = CASE
                    WHEN (CASE WHEN public.accounts_testmail.usage_month = :cur_month THEN public.accounts_testmail.usage_count + 1 ELSE 1 END) >= :near
                    THEN :end_of_month
                    ELSE public.accounts_testmail.cooldown_until
                  END,
                last_used = :now
            FROM candidate
            WHERE public.accounts_testmail.account_id = candidate.account_id
            RETURNING public.accounts_testmail.account_id AS id,
                      public.accounts_testmail.api_key AS connection_str,
                      public.accounts_testmail.usage_count,
                      public.accounts_testmail.usage_month
        """),
        {
            "cur_month": cur_month,
            "now": now,
            "quota": monthly_quota,
            "near": near,
            "end_of_month": _end_of_month_utc(),
        },
    )
    # Commit ngay — bump usage_count phải persistent trước khi session sau pick,
    # không thì rollback → count về 0 → round-robin pick lại cùng namespace.
    await session.commit()
    row = result.fetchone()
    if row is None:
        return None
    d = row._mapping
    return {
        "id": d["id"],
        "connection_str": d["connection_str"],
        "usage_count": d["usage_count"],
        "usage_month": d["usage_month"],
    }


async def increment_provider_usage_async(
    session: AsyncSession,
    provider_id: int,
    monthly_quota: int,
    near_quota_threshold: float = 0.9,
) -> dict[str, Any]:
    """Bump usage_count cho namespace (provider_id = accounts_testmail.account_id).

    Trả về {"usage_count": int, "cooldown": bool}.
    Sang tháng mới (usage_month khác) → reset về 1.
    """
    now = _now()
    cur_month = datetime.now(UTC).strftime("%Y-%m")
    near = max(1, int(monthly_quota * near_quota_threshold))

    result = await session.execute(
        text("""
            UPDATE public.accounts_testmail
            SET usage_count = CASE
                    WHEN usage_month = :cur_month THEN usage_count + 1
                    ELSE 1
                  END,
                usage_month = :cur_month,
                cooldown_until = CASE
                    WHEN (CASE WHEN usage_month = :cur_month THEN usage_count + 1 ELSE 1 END) >= :near
                    THEN :end_of_month
                    ELSE cooldown_until
                  END,
                last_used = :now
            WHERE account_id = :id
            RETURNING usage_count, usage_month, cooldown_until
        """),
        {
            "id": provider_id,
            "cur_month": cur_month,
            "near": near,
            "end_of_month": _end_of_month_utc(),
            "now": now,
        },
    )
    row = result.fetchone()
    d = row._mapping
    return {
        "usage_count": d["usage_count"],
        "cooldown": bool(d["cooldown_until"]),
    }


def _end_of_month_utc() -> str:
    """Đầu tháng sau (UTC), format cooldown_until dùng."""
    now = datetime.now(UTC)
    if now.month == 12:
        nm = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0)
    else:
        nm = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0)
    return nm.strftime("%Y-%m-%d %H:%M:%S UTC")