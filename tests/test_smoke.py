"""smoke/test_smoke.py — Smoke tests: import app, verify common exports, catch runtime breakage.

Chạy < 2s. Mục đích: phát hiện ngay nếu common package exports thiếu,
circular imports, hoặc module nào đéo import được sau refactor.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Inject common package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── common.database exports ────────────────────────────────────────────────

class TestCommonDatabaseExports:
    """Mọi function được dùng bởi services phải export từ __init__.py."""

    def test_import_init_db(self):
        from common.database import init_db
        assert callable(init_db)

    def test_import_account_crud(self):
        from common.database import (
            bulk_insert,
            count_accounts,
            delete_account,
            delete_accounts,
            delete_disabled_service_accounts,
            get_account_by_email,
            get_accounts,
            get_used_gmail_variations,
            insert_account,
            update_account,
            update_accounts_bulk,
            upsert_account,
        )

    def test_import_mailbox_functions(self):
        from common.database import (
            block_mailbox_for_service,
            delete_mailbox_record,
            get_available_mailboxes_for_service,
            get_mailbox_record,
            get_mailboxes,
            get_mailbox_google_auth_state,
            get_service_blocks,
            is_mailbox_blocked_for_service,
            save_mailbox_google_auth_state,
            unblock_mailbox_for_service,
            upsert_mailbox_record,
        )

    def test_import_sms_phone_functions(self):
        from common.database import delete_sms_phone, get_sms_phones, upsert_sms_phone

    def test_import_gmail_variations(self):
        from common.database import check_gmail_variations_availability

    def test_import_provider_functions(self):
        from common.database import (
            cycle_provider_tag,
            get_all_providers_with_tags,
            get_mail_providers,
            get_provider_domains,
            set_provider_domain_tags,
            update_provider,
            upsert_mail_provider,
        )

    def test_import_service_functions(self):
        from common.database import add_service, delete_service, get_distinct_services, service_exists


# ── common.enums ───────────────────────────────────────────────────────────

class TestCommonEnums:
    def test_import_google_page_state(self):
        from common.enums import GooglePageState
        assert hasattr(GooglePageState, "LOGIN_EMAIL")

    def test_google_page_state_values(self):
        from common.enums import GooglePageState
        assert GooglePageState.LOGIN_EMAIL.value == "login_email"


# ── common.exceptions ──────────────────────────────────────────────────────

class TestCommonExceptions:
    def test_import_app_error(self):
        from common.exceptions import AppError
        assert AppError is not None

    def test_import_error_code(self):
        from common.exceptions import ErrorCode
        assert ErrorCode is not None


# ── common.schemas ─────────────────────────────────────────────────────────

class TestCommonSchemas:
    def test_import_schemas(self):
        from common.schemas import ApiResponse
        resp = ApiResponse(success=True, data=None, error=None)
        assert resp.success is True