"""Per-user backend routes: Supabase session auth and service-role queries scoped by user."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from backend.routers import nessie, shopping_list
from backend.services import supabase_store as store


@pytest.fixture
def api(auth_headers):
    with TestClient(app) as client:
        client.headers.update(auth_headers)
        yield client


def _shopping_row(**overrides):
    row = {"id": str(uuid4()), "name": "Shoes", "price": 80.10, "brand": None, "category": "clothing",
           "allow_lower_quality": False, "completed": False}
    row.update(overrides)
    return row


@pytest.mark.parametrize("method, path", [
    ("get", "/api/shopping-list/items"), ("post", "/api/shopping-list/done"),
    ("get", "/api/spending/history"), ("get", "/api/nessie/transactions"), ("get", "/api/nessie/customers"),
])
def test_private_routes_require_a_supabase_session(api, supabase_mock, method, path):
    api.headers.pop("Authorization")
    assert getattr(api, method)(path).status_code == 401
    assert not supabase_mock.calls


def test_shopping_create_list_delete_are_scoped_to_the_user(api, supabase_mock, user_id):
    response = api.post("/api/shopping-list/items", json={"name": " Shoes ", "price": 80.10, "category": "clothing"})
    assert response.status_code == 201
    assert response.json()["name"] == "Shoes" and response.json()["price"] == 80.10
    insert = supabase_mock.calls[-1]
    assert (insert.method, insert.name) == ("POST", "shopping_items")
    assert insert.body["user_id"] == user_id and insert.body["price"] == "80.1"

    row = _shopping_row()
    supabase_mock.responses[("GET", "shopping_items")] = [row]
    assert api.get("/api/shopping-list/items").json() == [row]
    assert supabase_mock.calls[-1].params["user_id"] == f"eq.{user_id}"

    assert api.delete(f"/api/shopping-list/items/{row['id']}").status_code == 404
    delete = supabase_mock.calls[-1]
    assert delete.params["user_id"] == f"eq.{user_id}" and delete.params["id"] == f"eq.{row['id']}"
    supabase_mock.responses[("DELETE", "shopping_items")] = [row]
    assert api.delete(f"/api/shopping-list/items/{row['id']}").status_code == 204


def test_comparison_uses_serpapi_and_explains_items_without_prices(api, monkeypatch, supabase_mock):
    monkeypatch.setenv("SERPAPI_KEY", "fake-serp-key")
    priced, unpriced, done = _shopping_row(), _shopping_row(name="Milk", price=None), _shopping_row(completed=True)
    supabase_mock.responses[("GET", "shopping_items")] = [priced, unpriced, done]
    search = Mock(return_value=[])
    monkeypatch.setattr(shopping_list, "find_alternatives", search)
    response = api.post("/api/shopping-list/done")
    assert response.status_code == 200
    search.assert_called_once_with("Shoes", 80.10, None, allow_similar=False)
    items = response.json()["items"]
    assert [item["name"] for item in items] == ["Shoes", "Milk"]
    assert items[1]["original_price"] is None and "price" in items[1]["error"]


def test_bank_link_import_and_spending_history(api, monkeypatch, supabase_mock, user_id):
    monkeypatch.setattr(nessie, "accounts", Mock(return_value=[{"_id": "bank-account"}]))
    response = api.post("/api/nessie/link", json={"customer_id": "bank-customer", "account_id": "bank-account"})
    assert response.status_code == 200
    link = supabase_mock.calls[-1]
    assert (link.method, link.name, link.params["on_conflict"]) == ("POST", "linked_accounts", "user_id")
    assert link.body["user_id"] == user_id

    supabase_mock.responses[("GET", "linked_accounts")] = [{"customer_id": "bank-customer", "account_id": "bank-account"}]
    today = date.today().isoformat()
    purchase = {"_id": "p1", "amount": 10.25, "purchase_date": today}
    monkeypatch.setattr(nessie, "purchases", Mock(return_value=[purchase, purchase]))
    for name in ["deposits", "withdrawals", "transfers"]:
        monkeypatch.setattr(nessie, name, Mock(return_value=[]))
    supabase_mock.responses[("GET", "transactions")] = [
        {"external_id": "p1", "transaction_type": "purchase", "date": today, "amount": 10.25,
         "description": "Purchase", "category": "purchase", "source": "nessie"},
        {"external_id": "s1", "transaction_type": "income", "date": today, "amount": 1000,
         "description": "Salary", "category": "salary", "source": "nessie"},
    ]
    response = api.get("/api/nessie/transactions")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    upsert = next(call for call in supabase_mock.calls if call[:2] == ("POST", "transactions"))
    assert upsert.params["on_conflict"] == "user_id,source,external_id"
    assert len(upsert.body) == 1 and upsert.body[0]["user_id"] == user_id
    assert upsert.body[0]["external_id"] == "p1" and upsert.body[0]["raw_json"] == purchase
    reads = [call for call in supabase_mock.calls if call[:2] == ("GET", "transactions")]
    assert all(call.params["user_id"] == f"eq.{user_id}" for call in reads)

    history = api.get("/api/spending/history")
    assert history.status_code == 200
    assert Decimal(history.json()["total"]) == Decimal("10.25")
    assert Decimal(history.json()["income_total"]) == Decimal("1000")


def test_transactions_without_a_link_is_409(api):
    assert api.get("/api/nessie/transactions").status_code == 409


def test_database_outage_is_a_safe_503(api, supabase_mock):
    supabase_mock.failure = httpx.ReadTimeout("sb_secret_test_key_never_real private-host")
    response = api.get("/api/shopping-list/items")
    assert response.status_code == 503
    assert "sb_secret_test_key_never_real" not in response.text and "private-host" not in response.text


def test_transactions_preserve_precise_amounts_and_skip_missing_ids(supabase_mock, user_id):
    amount = Decimal("12345678901234567890.123456789")
    row = {"id": "bank-1", "source": "nessie", "type": "deposit", "amount": amount, "date": date.today(),
           "description": "Pay", "category": "salary", "raw": {"amount": amount, "when": date.today()}}
    assert store.upsert_transactions(user_id, [row, {"id": None}]) == 1
    sent = supabase_mock.calls[-1].body[0]
    assert sent["amount"] == str(amount) and sent["raw_json"]["amount"] == str(amount)
    supabase_mock.responses[("GET", "transactions")] = [{
        "external_id": "bank-1", "transaction_type": "deposit", "date": date.today().isoformat(),
        "amount": str(amount), "description": "Pay", "category": "salary", "source": "nessie",
    }]
    assert store.transactions(user_id)[0]["amount"] == amount
    assert store.upsert_transactions(user_id, [{"id": None}]) == 0
