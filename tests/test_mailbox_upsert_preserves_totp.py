"""
tests/test_mailbox_upsert_preserves_totp.py — Regression test for the
TOTP-wipe bug.

The bug: `upsert_mailbox_record` defaulted all settable parameters to "" or
False, and the SQLite on_conflict_do_update always wrote
totp_secret=totp_secret. A POST that did not mention totp_secret therefore
wiped the stored TOTP secret to "" on every subsequent upsert.

The fix: settable parameters now default to `_UNSET`; only fields the
caller actually passes are written on UPDATE.

This test exercises the contract end-to-end on a temp SQLite DB.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Inject common package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    from common.database import init_db
    init_db(p)
    return p


class TestMailboxUpsertPreservesTOTP:
    def test_seed_then_upsert_without_totp_preserves_secret(self, db_path):
        from common.database import upsert_mailbox_record, get_mailbox_record

        upsert_mailbox_record(
            db_path, "user@gmail.com",
            app_password="pw1", totp_secret="JBSWY3DPEHPK3PXP",
        )
        # Second upsert that does NOT mention totp_secret: secret must survive.
        upsert_mailbox_record(
            db_path, "user@gmail.com",
            app_password="pw2",
        )
        rec = get_mailbox_record(db_path, "user@gmail.com")
        assert rec is not None
        assert rec["totp_secret"] == "JBSWY3DPEHPK3PXP", (
            "TOTP secret was wiped by an upsert that did not pass it"
        )
        assert rec["app_password"] == "pw2"

    def test_explicit_empty_string_clears_totp(self, db_path):
        from common.database import upsert_mailbox_record, get_mailbox_record

        upsert_mailbox_record(
            db_path, "user@gmail.com",
            app_password="pw1", totp_secret="JBSWY3DPEHPK3PXP",
        )
        # An empty string is a deliberate clear.
        upsert_mailbox_record(db_path, "user@gmail.com", totp_secret="")
        rec = get_mailbox_record(db_path, "user@gmail.com")
        assert rec is not None
        assert rec["totp_secret"] == ""

    def test_upsert_preserves_app_password_too(self, db_path):
        from common.database import upsert_mailbox_record, get_mailbox_record

        upsert_mailbox_record(
            db_path, "user@gmail.com",
            app_password="first", totp_secret="JBSWY3DPEHPK3PXP",
        )
        # Subsequent upsert that changes totp but does not mention app_password.
        upsert_mailbox_record(db_path, "user@gmail.com", totp_secret="NEW")
        rec = get_mailbox_record(db_path, "user@gmail.com")
        assert rec is not None
        assert rec["totp_secret"] == "NEW"
        assert rec["app_password"] == "first", (
            "app_password was wiped by an upsert that did not pass it"
        )
