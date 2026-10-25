"""Explicit opt-in only; never writes or deletes cloud data."""

import os

import httpx
import pytest

from app import database, storage

pytestmark = pytest.mark.integration


@pytest.fixture
def configured_supabase(monkeypatch):
    url = os.getenv("TEST_SUPABASE_URL")
    key = os.getenv("TEST_SUPABASE_SECRET_KEY")
    if not url or not key:
        pytest.skip("Set TEST_SUPABASE_URL and TEST_SUPABASE_SECRET_KEY for HTTPS checks.")
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", key)
    assert database.check_connection()["status"] == "ok"
    return url.rstrip("/")


def test_live_https_schema_and_read_operations(configured_supabase):
    assert isinstance(storage.list_receipts(), list)
    assert isinstance(storage.list_items(None, None, None), list)
    assert storage.spending_summary("all")["period"] == "all"


def test_publishable_key_cannot_read_receipts_or_call_rpcs(configured_supabase):
    key = os.getenv("TEST_SUPABASE_PUBLISHABLE_KEY")
    if not key:
        pytest.skip("Set TEST_SUPABASE_PUBLISHABLE_KEY for anonymous access checks.")
    with httpx.Client(timeout=15, headers={"apikey": key}) as client:
        response = client.get(configured_supabase + "/rest/v1/receipts", params={"select": "id", "limit": "1"})
        assert response.status_code in {401, 403, 404}
        response = client.post(configured_supabase + "/rest/v1/rpc/ripple_receipts", json={})
        assert response.status_code in {401, 403, 404}
