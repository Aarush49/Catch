"""Regression tests for main's API backed by the Supabase HTTPS adapter."""

import hashlib
from datetime import date
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from app.database import DatabaseError
from backend.models import ParsedReceipt
from backend.routers import nessie, receipts, shopping_list
from backend.services import supabase_store as store


@pytest.fixture
def account(user):
    return {"id": user["id"], "email": "person@example.com"}


@pytest.fixture
def api(supabase_mock, account):
    supabase_mock.responses["ripple_session_user"] = account
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test-session-token"
        yield client


def test_signup_preserves_contract_and_hashes_credentials(api, supabase_mock, account):
    supabase_mock.responses["ripple_create_account"] = account
    supabase_mock.responses["ripple_create_session"] = {"status": "ok"}
    response = api.post("/api/auth/signup", json={"email": account["email"], "password": "Password123!"})
    assert response.status_code == 201
    body = response.json()
    assert body["user"] == account
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    name, params = supabase_mock.calls[0]
    assert name == "ripple_create_account"
    assert len(params["p_salt"]) == 32
    assert params["p_password_hash"] == store._hash("Password123!", bytes.fromhex(params["p_salt"]))
    name, params = supabase_mock.calls[1]
    assert name == "ripple_create_session"
    assert params["p_token_hash"] == hashlib.sha256(body["access_token"].encode()).hexdigest()
    assert "Password123!" not in str(supabase_mock.calls)
    assert "password_hash" not in response.text
    assert body["access_token"] not in str(supabase_mock.calls)


def test_duplicate_signup_is_409(api, supabase_mock, account):
    supabase_mock.responses["ripple_create_account"] = {"code": "23505", "message": "private detail", "details": None, "hint": None}
    supabase_mock.status = 400
    response = api.post("/api/auth/signup", json={"email": account["email"], "password": "Password123!"})
    assert response.status_code == 409
    assert "private detail" not in response.text


def test_login_rejects_wrong_password_and_creates_session_for_correct_password(api, supabase_mock, account):
    salt = bytes.fromhex("01" * 16)
    supabase_mock.responses["ripple_auth_record"] = {**account, "salt": salt.hex(), "password_hash": store._hash("Password123!", salt)}
    supabase_mock.responses["ripple_create_session"] = {"status": "ok"}
    assert api.post("/api/auth/login", json={"email": account["email"], "password": "Incorrect123!"}).status_code == 401
    response = api.post("/api/auth/login", json={"email": account["email"], "password": "Password123!"})
    assert response.status_code == 200
    assert response.json()["user"] == account
    assert response.json()["access_token"]


def test_session_me_logout_and_expiry(api, supabase_mock, account):
    assert api.get("/api/auth/me").json() == account
    assert supabase_mock.calls[-1] == ("ripple_session_user", {"p_token_hash": hashlib.sha256(b"test-session-token").hexdigest()})
    supabase_mock.responses["ripple_delete_session"] = {"status": "ok"}
    assert api.post("/api/auth/logout").status_code == 204
    supabase_mock.responses["ripple_session_user"] = None
    assert api.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("path", ["/api/receipts", "/api/shopping-list/items", "/api/spending/history", "/api/nessie/transactions"])
def test_private_routes_require_a_session(api, path):
    api.headers.pop("Authorization")
    assert api.get(path).status_code == 401


def test_receipt_scan_is_atomic_retains_carbon_and_uses_current_user(api, monkeypatch, supabase_mock, account):
    monkeypatch.setattr(receipts, "parse_receipt", Mock(return_value=ParsedReceipt.model_validate({
        "store": "Hardware", "date": "2026-10-24", "total": "12.34",
        "items": [{"name": "Light bulb", "price": "12.34", "category": "utilities"}],
    })))
    response = api.post("/api/receipts/scan", files={"file": ("receipt.png", b"image", "image/png")})
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {"id", "store", "date", "total", "created_at", "items"}
    assert data["store"] == "Hardware"
    assert data["items"][0]["name"] == "Light bulb"
    assert Decimal(data["items"][0]["carbon_kg_co2e"]) >= 0
    writes = [(name, params) for name, params in supabase_mock.calls if name == "ripple_save_receipt"]
    assert len(writes) == 1
    assert writes[0][1]["p_user_id"] == account["id"]
    assert "carbon_kg_co2e" in writes[0][1]["p_receipt"]["items"][0]


def test_receipt_history_and_detail_are_scoped(api, supabase_mock, account, saved_receipt):
    supabase_mock.responses["ripple_receipts"] = [saved_receipt]
    history = api.get("/api/receipts")
    assert history.status_code == 200
    assert supabase_mock.calls[-1][1]["p_user_id"] == account["id"]
    detail = api.get(f"/api/receipts/{saved_receipt['id']}")
    assert detail.json() == history.json()[0]
    assert supabase_mock.calls[-1][1]["p_receipt_id"] == saved_receipt["id"]
    supabase_mock.responses["ripple_receipts"] = []
    assert api.get(f"/api/receipts/{saved_receipt['id']}").status_code == 404


def _shopping_row(account):
    return {"id": str(uuid4()), "user_id": account["id"], "name": "Shoes", "price": "80.10",
            "brand": None, "category": "clothing", "allow_lower_quality": False}


def test_shopping_create_list_delete_contracts(api, supabase_mock, account):
    row = _shopping_row(account)
    supabase_mock.responses["ripple_add_shopping_item"] = row
    response = api.post("/api/shopping-list/items", json={"name": "Shoes", "price": 80.10, "category": "clothing"})
    assert response.status_code == 201
    assert response.json()["price"] == 80.10
    assert "user_id" not in response.json()
    assert supabase_mock.calls[-1][1]["p_user_id"] == account["id"]
    supabase_mock.responses["ripple_shopping_items"] = [row]
    assert api.get("/api/shopping-list/items").json() == [row | {"price": 80.10}]
    supabase_mock.responses["ripple_delete_shopping_item"] = {"deleted": False}
    assert api.delete(f"/api/shopping-list/items/{row['id']}").status_code == 404
    assert supabase_mock.calls[-1][1]["p_user_id"] == account["id"]
    supabase_mock.responses["ripple_delete_shopping_item"] = {"deleted": True}
    assert api.delete(f"/api/shopping-list/items/{row['id']}").status_code == 204


def test_shopping_comparison_still_uses_serpapi(api, monkeypatch, supabase_mock, account):
    monkeypatch.setenv("SERPAPI_KEY", "fake-serp-key")
    supabase_mock.responses["ripple_shopping_items"] = [_shopping_row(account)]
    search = Mock(return_value=[])
    monkeypatch.setattr(shopping_list, "find_alternatives", search)
    response = api.post("/api/shopping-list/done")
    assert response.status_code == 200
    search.assert_called_once_with("Shoes", 80.10, None, allow_similar=False)


def test_bank_link_import_upsert_and_spending_history(api, monkeypatch, supabase_mock, account):
    monkeypatch.setattr(nessie, "accounts", Mock(return_value=[{"_id": "bank-account"}]))
    supabase_mock.responses["ripple_save_link"] = {"status": "ok"}
    response = api.post("/api/nessie/link", json={"customer_id": "bank-customer", "account_id": "bank-account"})
    assert response.status_code == 200
    supabase_mock.responses["ripple_get_link"] = {"customer_id": "bank-customer", "account_id": "bank-account"}
    monkeypatch.setattr(nessie, "purchases", Mock(return_value=[{"_id": "p1", "amount": 10.25, "purchase_date": date.today().isoformat()}]))
    for name in ["deposits", "withdrawals", "transfers"]:
        monkeypatch.setattr(nessie, name, Mock(return_value=[]))
    supabase_mock.responses["ripple_upsert_transactions"] = {"count": 1}
    txns = [{"id": "p1", "source": "nessie", "type": "purchase", "amount": "10.25", "date": date.today().isoformat(), "description": "Purchase", "category": "groceries"},
            {"id": "s1", "source": "nessie", "type": "income", "amount": "1000.00", "date": date.today().isoformat(), "description": "Salary", "category": "salary"}]
    supabase_mock.responses["ripple_transactions"] = txns
    response = api.get("/api/nessie/transactions")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    imports = [params for name, params in supabase_mock.calls if name == "ripple_upsert_transactions"]
    assert imports[0]["p_user_id"] == account["id"]
    assert imports[0]["p_rows"][0]["id"] == "p1"
    history = api.get("/api/spending/history")
    assert history.status_code == 200
    assert Decimal(history.json()["total"]) == Decimal("10.25")
    assert Decimal(history.json()["income_total"]) == Decimal("1000.00")


def test_failed_auth_database_request_is_safe_503(api, supabase_mock):
    supabase_mock.failure = httpx.ReadTimeout("sb_secret_test_key_never_real")
    response = api.get("/api/auth/me")
    assert response.status_code == 503
    assert "sb_secret_test_key_never_real" not in response.text


def test_transactions_preserve_precise_amounts_and_skip_missing_external_ids(supabase_mock, account):
    amount = Decimal("12345678901234567890.123456789")
    row = {"id": "bank-1", "source": "nessie", "type": "deposit", "amount": amount, "date": date.today(), "description": "Pay", "category": "salary"}
    supabase_mock.responses["ripple_upsert_transactions"] = {"count": 1}
    assert store.upsert_transactions(account["id"], [row, {"id": None}]) == 1
    assert supabase_mock.calls[-1][1]["p_rows"][0]["amount"] == str(amount)
    supabase_mock.responses["ripple_transactions"] = [{**row, "date": date.today().isoformat(), "amount": str(amount)}]
    assert store.transactions(account["id"])[0]["amount"] == amount


def test_both_entry_points_use_the_same_supabase_application():
    from app.main import app as original_app
    assert app is original_app
    paths = app.openapi()["paths"]
    assert all(path in paths for path in ["/receipts", "/api/auth/signup", "/api/receipts", "/api/shopping/alternatives", "/api/spending/history"])


def test_unconfirmed_session_write_is_rejected(supabase_mock, account):
    supabase_mock.responses["ripple_create_session"] = {}
    with pytest.raises(DatabaseError):
        store.create_session(account["id"])
