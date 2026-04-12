"""common.database — SQLAlchemy ORM, migrations, and CRUD for accounts.db."""
from __future__ import annotations

from ._accounts import (
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
from ._engine import (
    _Account,
    _MailProvider,
    _MailboxServiceBlock,
    _ProviderDomainTag,
    _Service,
    _get_engine,
    _now,
    _to_dict,
    _to_mailbox_dict,
    _to_provider_dict,
)
from ._mailboxes import (
    block_mailbox_for_service,
    get_mailbox_record,
    is_mailbox_blocked_for_service,
    unblock_mailbox_for_service,
    upsert_mailbox_record,
)
from ._migrations import init_db
from ._providers import (
    cycle_provider_tag,
    get_all_providers_with_tags,
    get_mail_providers,
    get_provider_domains,
    set_provider_domain_tags,
    update_provider,
    upsert_mail_provider,
)
from ._services import add_service, delete_service, get_distinct_services, service_exists