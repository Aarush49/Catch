"""Compatibility import for older callers; persistence now uses Supabase HTTPS."""

from backend.services.supabase_store import (
    add_shopping_item, authenticate, create_session, create_user, delete_session,
    delete_shopping_item, get_link, get_receipt, ledger_entries, list_receipts,
    list_shopping_items, save_link, save_receipt, session_user, transactions,
    upsert_transactions,
)
