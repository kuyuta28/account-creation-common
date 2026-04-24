"""common.database — SQLAlchemy ORM, migrations, and CRUD for accounts.db."""
from __future__ import annotations

from ._accounts import (  # noqa: F401
    bulk_insert,
    check_gmail_variations_availability,
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
from ._engine import (  # noqa: F401
    _Account,
    _MailProvider,
    _MailboxServiceBlock,
    _ProviderDomainTag,
    _Service,
    _engines,
    _get_engine,
    _now,
    _to_dict,
    _to_mailbox_dict,
    _to_provider_dict,
)
from ._mailboxes import (  # noqa: F401
    block_mailbox_for_service,
    delete_mailbox_record,
    delete_sms_phone,
    get_available_mailboxes_for_service,
    get_mailbox_record,
    get_mailboxes,
    get_mailbox_google_auth_state,
    get_service_blocks,
    get_sms_phones,
    is_mailbox_blocked_for_service,
    save_mailbox_google_auth_state,
    unblock_mailbox_for_service,
    upsert_mailbox_record,
    upsert_sms_phone,
)
from ._migrations import init_db  # noqa: F401
from ._providers import (  # noqa: F401
    cycle_provider_tag,
    get_all_providers_with_tags,
    get_mail_providers,
    get_provider_domains,
    set_provider_domain_tags,
    update_provider,
    upsert_mail_provider,
)
from ._services import add_service, delete_service, get_distinct_services, service_exists  # noqa: F401