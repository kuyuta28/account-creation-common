"""
context.py — Enterprise-grade application context container.

Design principles:
1. Immutable config (frozen dataclass)
2. Structured state managers (not scattered dicts)
3. Lifecycle-aware (init → use → shutdown)
4. Testable (mockable managers)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol
from collections.abc import AsyncIterator


class LifecycleManager(Protocol):
    async def init(self) -> None: ...

    async def shutdown(self) -> None: ...


@dataclass(frozen=True)
class AppContext:
    """Immutable container — single source of truth for all dependencies."""
    config: Any
    db_engine: Any
    mail_state: LifecycleManager | None = None
    mailbox_store: LifecycleManager | None = None
    job_state: LifecycleManager | None = None
    image_lab_manager: LifecycleManager | None = None
    shutdown_handlers: tuple[Callable[[], Any], ...] = field(default_factory=tuple)


# ── Global singleton ────────────────────────────────────────────────

_container: AppContext | None = None


def init_app_context(
    config: Any,
    db_engine: Any,
    mail_state: LifecycleManager | None = None,
    mailbox_store: LifecycleManager | None = None,
    job_state: LifecycleManager | None = None,
    image_lab_manager: LifecycleManager | None = None,
) -> AppContext:
    global _container
    _container = AppContext(
        config=config,
        db_engine=db_engine,
        mail_state=mail_state,
        mailbox_store=mailbox_store,
        job_state=job_state,
        image_lab_manager=image_lab_manager,
        shutdown_handlers=(),
    )
    return _container


def get_app_context() -> AppContext:
    if _container is None:
        raise RuntimeError("AppContext not initialized — call init_app_context() first")
    return _container


# ── Lifecycle ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan_context(_app: Any) -> AsyncIterator[AppContext]:
    """FastAPI lifespan — init → yield → shutdown."""
    ctx = get_app_context()

    # Startup: init all state managers
    if ctx.mail_state:
        await ctx.mail_state.init()
    if ctx.mailbox_store:
        await ctx.mailbox_store.init()
    if ctx.job_state:
        await ctx.job_state.init()
    if ctx.image_lab_manager:
        await ctx.image_lab_manager.init()

    yield ctx

    # Graceful shutdown in reverse order
    if ctx.image_lab_manager:
        await ctx.image_lab_manager.shutdown()
    if ctx.job_state:
        await ctx.job_state.shutdown()
    if ctx.mailbox_store:
        await ctx.mailbox_store.shutdown()
    if ctx.mail_state:
        await ctx.mail_state.shutdown()
