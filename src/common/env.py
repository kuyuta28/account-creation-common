"""
common/src/common/env.py — Environment configuration for all services.

Loads APP_ENV from .env or environment variables.
Provides DB path resolution and env-specific settings.

Usage:
    from common.env import APP_ENV, db_path

    # db_path resolves to: data/accounts_{APP_ENV}.db
    # e.g., data/accounts_dev.db, data/accounts_test.db
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

# ── Environment ─────────────────────────────────────────────────────────────────

# Valid environments
Env = Literal["dev", "prod", "test"]

def _load_env() -> Env:
    """Load APP_ENV and DATABASE_URL from environment or .env file."""
    # Check .env file first (project root AND service subdirectories)
    env_paths = [
        Path(__file__).resolve().parent.parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent.parent / "registrar" / ".env",
        Path(__file__).resolve().parent.parent.parent.parent / "mail-service" / ".env",
        Path(__file__).resolve().parent.parent.parent.parent / "tts-proxy" / ".env",
        Path(__file__).resolve().parent.parent.parent.parent / "aa-proxy" / ".env",
    ]
    for env_file in env_paths:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    value = value.strip()
                    # Load DATABASE_URL if not already set
                    if key == "DATABASE_URL" and key not in os.environ:
                        os.environ[key] = value
                    # Load APP_ENV only if not already set
                    elif key == "APP_ENV" and key not in os.environ:
                        os.environ[key] = value.strip()
                        break

    raw = os.getenv("APP_ENV", "prod").lower()
    if raw in ("dev", "prod", "test"):
        return raw
    return "prod"

APP_ENV: Env = _load_env()

# ── Database Path ───────────────────────────────────────────────────────────────

def _resolve_db_base() -> Path:
    """Get the base directory for DB files (service root)."""
    # Called from common/src/common/env.py
    # Go up: common/src/common/env.py → common/src → common → project root
    return Path(__file__).resolve().parent.parent.parent.parent


def db_path(env: Env | None = None) -> Path:
    """Return path to accounts DB for given environment.

    Usage:
        db_path()         → uses APP_ENV (default)
        db_path("dev")    → data/accounts_dev.db
        db_path("test")   → data/accounts_test.db
        db_path("prod")   → data/accounts.db (no suffix for prod)
    """
    target_env = env or APP_ENV
    base = _resolve_db_base()

    if target_env == "prod":
        return base / "data" / "accounts.db"
    return base / "data" / f"accounts_{target_env}.db"


def mail_db_path(env: Env | None = None) -> Path:
    """Return path to mail DB for given environment."""
    target_env = env or APP_ENV
    base = _resolve_db_base()

    if target_env == "prod":
        return base / "mail-service" / "data" / "mail.db"
    return base / "mail-service" / "data" / f"mail_{target_env}.db"


# ── Env Info ────────────────────────────────────────────────────────────────────

IS_DEV = APP_ENV == "dev"
IS_TEST = APP_ENV == "test"
IS_PROD = APP_ENV == "prod"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if IS_DEV else "WARNING")