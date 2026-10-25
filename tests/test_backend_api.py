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
from backend.services import nessie_service, supabase_store as store
from backend.services.nessie_service import next_due_date


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
    for name in ["deposits", "withdrawals", "transfers", "bills"]:
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


class FakeBank:
    """An in-memory Nessie: every create call is visible to the matching list call."""

    def __init__(self, monkeypatch, *, purchase_error=None, transfer_error=None, existing_nickname=None):
        self.accounts: dict[str, dict] = {}
        self.records: dict[tuple[str, str], list] = {}
        self.purchase_error, self.transfer_error = purchase_error, transfer_error
        if existing_nickname:
            self.accounts["demo-account"] = {"_id": "demo-account", "type": "Checking", "nickname": existing_nickname}
        self.mocks = {
            "merchants": Mock(return_value=[{"_id": "m-heb", "name": "H-E-B"}, {"_id": "m-other", "name": "Somewhere else"}]),
            "create_merchant": Mock(side_effect=lambda name, category: {"_id": f"m-{name}"}),
            "merchant_category": Mock(side_effect=lambda merchant_id: {"m-heb": "groceries", "m-Shell": "transportation"}.get(merchant_id, "other")),
            "create_customer": Mock(return_value={"_id": "demo-customer"}),
            "create_account": Mock(side_effect=self.create_account),
            "accounts": Mock(side_effect=lambda customer_id: list(self.accounts.values())),
            "account": Mock(side_effect=lambda account_id: self.accounts[account_id]),
            "create_purchase": Mock(side_effect=self.create_purchase),
            "create_deposit": Mock(side_effect=lambda account_id, amount, day, description: self.add(
                account_id, "deposits", {"amount": amount, "transaction_date": day.isoformat(), "description": description, "status": "completed"})),
            "create_bill": Mock(side_effect=self.create_bill),
            "create_transfer": Mock(side_effect=self.create_transfer),
        }
        for kind in ["purchases", "deposits", "withdrawals", "transfers", "bills"]:
            self.mocks[kind] = Mock(side_effect=lambda account_id, kind=kind: list(self.records.get((account_id, kind), [])))
        for name, mock in self.mocks.items():
            monkeypatch.setattr(nessie, name, mock)

    def add(self, account_id, kind, record):
        rows = self.records.setdefault((account_id, kind), [])
        record = {**record, "_id": f"{account_id}-{kind}-{len(rows)}"}
        rows.append(record)
        return record

    def create_account(self, customer_id, nickname, balance, account_type="Checking"):
        account_id = "demo-account" if account_type == "Checking" else "demo-savings"
        self.accounts[account_id] = {"_id": account_id, "type": account_type, "nickname": nickname, "balance": balance}
        return self.accounts[account_id]

    def create_purchase(self, account_id, merchant_id, amount, day, description):
        if self.purchase_error:
            raise self.purchase_error
        return self.add(account_id, "purchases", {"merchant_id": merchant_id, "amount": amount, "purchase_date": day.isoformat(),
                                                   "description": description, "status": "completed"})

    def create_bill(self, account_id, payee, nickname, amount, day, today):
        due = next_due_date(day, today)
        return self.add(account_id, "bills", {"status": "recurring", "payee": payee, "nickname": nickname, "recurring_date": day,
                                               "payment_amount": amount, "upcoming_payment_date": due.isoformat()})

    def create_transfer(self, account_id, amount, day, description):
        if self.transfer_error:
            raise self.transfer_error
        return self.add(account_id, "transfers", {"amount": amount, "transaction_date": day.isoformat(),
                                                   "description": description, "status": "completed"})


def _upserted(supabase_mock):
    return [row for call in supabase_mock.calls if call[:2] == ("POST", "transactions") for row in call.body]


def test_demo_bank_creates_seeds_links_and_imports(api, monkeypatch, supabase_mock, user_id):
    bank = FakeBank(monkeypatch)
    response = api.post("/api/nessie/demo-bank")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] is True and body["account_id"] == "demo-account"
    assert body["count"] == 15 + 1 + len(nessie.DEMO_BILLS)

    # Existing merchants are reused by name; only the missing demo merchants are created.
    created_names = [call.args[0] for call in bank.mocks["create_merchant"].call_args_list]
    assert "H-E-B" not in created_names and len(created_names) == len(nessie.DEMO_MERCHANTS) - 1
    assert [call.args for call in bank.mocks["create_account"].call_args_list] == [
        ("demo-customer", "Catch demo checking", 2500), ("demo-customer", "Catch savings", 0, "Savings")]
    purchases = bank.mocks["create_purchase"].call_args_list
    assert len(purchases) == 15
    assert all(call.args[0] == "demo-account" for call in purchases)
    assert all(isinstance(call.args[2], int) and call.args[2] > 0 for call in purchases)
    assert all(call.args[3] < date.today() for call in purchases)
    assert purchases[0].args[1] == "m-heb" and purchases[1].args[1] == "m-Starbucks"
    bank.mocks["create_deposit"].assert_called_once()
    bills = bank.mocks["create_bill"].call_args_list
    assert [(call.args[1], call.args[3], call.args[4]) for call in bills] == [(p, a, d) for p, _, a, d in nessie.DEMO_BILLS]
    assert all(call.args[0] == "demo-account" for call in bills)

    link = next(call for call in supabase_mock.calls if call[:2] == ("POST", "linked_accounts"))
    assert link.body == {"user_id": user_id, "provider": "nessie", "customer_id": "demo-customer", "account_id": "demo-account"}
    rows = _upserted(supabase_mock)
    assert all(row["user_id"] == user_id for row in rows)
    paycheck = next(row for row in rows if row["transaction_type"] == "income")
    assert (paycheck["category"], paycheck["amount"]) == ("salary", "1850")
    assert {row["transaction_type"] for row in rows} == {"purchase", "income", "bill"}
    # Purchases carry their merchant's spending category.
    categories = {row["description"]: row["category"] for row in rows if row["transaction_type"] == "purchase"}
    assert categories["H-E-B"] == "groceries" and categories["Shell"] == "transportation" and categories["Target"] == "other"
    rent = next(row for row in rows if row["transaction_type"] == "bill" and row["description"] == "Rent")
    assert rent["amount"] == "950.0" and rent["category"] == "bill"
    # Bills that Nessie no longer returns are removed from Supabase.
    prune = next(call for call in supabase_mock.calls if call[:2] == ("DELETE", "transactions"))
    assert prune.params["user_id"] == f"eq.{user_id}" and prune.params["transaction_type"] == "eq.bill"
    assert prune.params["external_id"].startswith("not.in.(") and "demo-account-bills-0" in prune.params["external_id"]


def test_demo_bank_twice_refreshes_instead_of_creating_a_second_bank(api, monkeypatch, supabase_mock):
    bank = FakeBank(monkeypatch)
    assert api.post("/api/nessie/demo-bank").status_code == 200
    for mock in bank.mocks.values():
        mock.reset_mock()
    supabase_mock.calls.clear()
    supabase_mock.responses[("GET", "linked_accounts")] = [{"customer_id": "demo-customer", "account_id": "demo-account"}]
    response = api.post("/api/nessie/demo-bank")
    assert response.status_code == 200
    assert response.json()["created"] is False and response.json()["account_id"] == "demo-account"
    for name in ["merchants", "create_merchant", "create_customer", "create_account", "create_purchase", "create_deposit", "create_bill"]:
        bank.mocks[name].assert_not_called()
    bank.mocks["purchases"].assert_called_once_with("demo-account")
    assert not any(call[:2] == ("POST", "linked_accounts") for call in supabase_mock.calls)


def test_refresh_adds_bills_to_an_older_demo_bank_only(api, monkeypatch, supabase_mock):
    supabase_mock.responses[("GET", "linked_accounts")] = [{"customer_id": "demo-customer", "account_id": "demo-account"}]
    bank = FakeBank(monkeypatch, existing_nickname="Catch demo checking")
    assert api.post("/api/nessie/demo-bank").status_code == 200
    assert bank.mocks["create_bill"].call_count == len(nessie.DEMO_BILLS)
    assert api.post("/api/nessie/demo-bank").status_code == 200
    assert bank.mocks["create_bill"].call_count == len(nessie.DEMO_BILLS)

    hand_linked = FakeBank(monkeypatch, existing_nickname="My own sandbox account")
    assert api.post("/api/nessie/demo-bank").status_code == 200
    hand_linked.mocks["create_bill"].assert_not_called()


def test_savings_move_rounds_to_dollars_and_records_both_sides(api, monkeypatch, supabase_mock, user_id):
    supabase_mock.responses[("GET", "linked_accounts")] = [{"customer_id": "demo-customer", "account_id": "demo-account"}]
    bank = FakeBank(monkeypatch, existing_nickname="Catch demo checking")
    supabase_mock.responses[("GET", "transactions")] = [
        {"external_id": "s1", "transaction_type": "savings", "date": date.today().isoformat(), "amount": 7,
         "description": "To savings", "category": "savings", "source": "nessie"},
        {"external_id": "s0", "transaction_type": "savings", "date": date.today().isoformat(), "amount": 3,
         "description": "To savings", "category": "savings", "source": "nessie"},
        {"external_id": "p1", "transaction_type": "purchase", "date": date.today().isoformat(), "amount": 50,
         "description": "H-E-B", "category": "groceries", "source": "nessie"},
    ]
    response = api.post("/api/nessie/savings", json={"amount": 7.49, "description": "Tide Pods → Tide Free & Gentle"})
    assert response.status_code == 200, response.text
    assert response.json()["moved"] == 7 and Decimal(str(response.json()["savings_total"])) == Decimal("10")
    # The savings account is created on first use, then receives the deposit; checking records the transfer.
    bank.mocks["create_account"].assert_called_once_with("demo-customer", "Catch savings", 0, "Savings")
    deposit = bank.mocks["create_deposit"].call_args
    assert deposit.args[:2] == ("demo-savings", 7) and deposit.args[3] == "To savings: Tide Pods → Tide Free & Gentle"
    assert bank.mocks["create_transfer"].call_args.args[:2] == ("demo-account", 7)
    savings_rows = [row for row in _upserted(supabase_mock) if row["transaction_type"] == "savings"]
    assert len(savings_rows) == 1 and savings_rows[0]["amount"] == "7" and savings_rows[0]["category"] == "savings"

    assert api.post("/api/nessie/savings", json={"amount": 2.5}).json()["moved"] == 3
    bank.mocks["create_account"].assert_called_once()  # the existing savings account is reused


def test_savings_under_half_a_dollar_moves_nothing(api, monkeypatch, supabase_mock):
    supabase_mock.responses[("GET", "linked_accounts")] = [{"customer_id": "demo-customer", "account_id": "demo-account"}]
    bank = FakeBank(monkeypatch, existing_nickname="Catch demo checking")
    response = api.post("/api/nessie/savings", json={"amount": 0.49})
    assert response.status_code == 200 and response.json()["moved"] == 0
    for name in ["create_account", "create_deposit", "create_transfer"]:
        bank.mocks[name].assert_not_called()


def test_savings_needs_a_linked_bank_and_a_valid_amount(api, monkeypatch, supabase_mock):
    FakeBank(monkeypatch)
    response = api.post("/api/nessie/savings", json={"amount": 5})
    assert response.status_code == 409 and "Connect a demo bank" in response.json()["detail"]
    supabase_mock.responses[("GET", "linked_accounts")] = [{"customer_id": "demo-customer", "account_id": "demo-account"}]
    for amount in [0, -3, 100_001]:
        assert api.post("/api/nessie/savings", json={"amount": amount}).status_code == 422
    api.headers.pop("Authorization")
    assert api.post("/api/nessie/savings", json={"amount": 5}).status_code == 401


def test_savings_still_succeeds_when_the_checking_transfer_fails(api, monkeypatch, supabase_mock):
    supabase_mock.responses[("GET", "linked_accounts")] = [{"customer_id": "demo-customer", "account_id": "demo-account"}]
    bank = FakeBank(monkeypatch, existing_nickname="Catch demo checking",
                    transfer_error=nessie.NessieServiceError("Bank sandbox request failed.", 502))
    response = api.post("/api/nessie/savings", json={"amount": 4})
    assert response.status_code == 200 and response.json()["moved"] == 4
    bank.mocks["create_deposit"].assert_called_once()


def test_demo_bank_failure_saves_no_link_so_it_can_be_retried(api, monkeypatch, supabase_mock):
    FakeBank(monkeypatch, purchase_error=nessie.NessieServiceError("Bank sandbox request failed.", 502))
    response = api.post("/api/nessie/demo-bank")
    assert response.status_code == 502 and response.json()["detail"] == "Bank sandbox request failed."
    assert not any(call.method == "POST" for call in supabase_mock.calls)


def test_demo_bank_requires_a_session(api, supabase_mock):
    api.headers.pop("Authorization")
    assert api.post("/api/nessie/demo-bank").status_code == 401


def test_nessie_client_request_shapes_and_missing_transfers(monkeypatch):
    from backend.services import nessie_service
    monkeypatch.setenv("NESSIE_API_KEY", "fake-nessie-key")
    sent = []

    def fake_request(method, url, params=None, json=None, timeout=None):
        sent.append((method, url, json))
        request = httpx.Request(method, url)
        if method == "GET" and (url.endswith("/transfers") or url.endswith("/missing/purchases")):
            return httpx.Response(404, text='"No transfers found for this account"', request=request)
        if method == "POST":
            return httpx.Response(201, json={"code": 201, "objectCreated": {**json, "_id": "new-id"}}, request=request)
        return httpx.Response(200, json=[], request=request)

    monkeypatch.setattr(nessie_service.httpx, "request", fake_request)
    created = nessie_service.create_purchase("acct", "merchant", 12, date(2026, 10, 20), "H-E-B")
    assert created["_id"] == "new-id"
    assert sent[-1] == ("POST", "https://api.nessieisreal.com/accounts/acct/purchases", {
        "merchant_id": "merchant", "medium": "balance", "purchase_date": "2026-10-20",
        "amount": 12, "status": "completed", "description": "H-E-B"})
    nessie_service.create_deposit("acct", 1850, date(2026, 10, 11), "Payroll paycheck")
    assert sent[-1][2]["status"] == "completed" and sent[-1][2]["transaction_date"] == "2026-10-11"
    assert nessie_service.create_customer("Catch", "Demo")["address"]["state"] == "TX"
    assert nessie_service.create_merchant("H-E-B", "Groceries")["category"] == "Groceries"
    assert nessie_service.transfers("acct") == []
    # Only transfers treat 404 as empty; a missing account elsewhere is still an error.
    with pytest.raises(nessie_service.NessieServiceError):
        nessie_service.purchases("missing")

    nessie_service.create_bill("acct", "Rent", "Rent", 950.0, 1, date(2026, 10, 25))
    assert sent[-1] == ("POST", "https://api.nessieisreal.com/accounts/acct/bills", {
        "status": "recurring", "payee": "Rent", "nickname": "Rent", "payment_date": "2026-11-01",
        "recurring_date": 1, "payment_amount": 950.0})
    nessie_service.create_transfer("acct", 7, date(2026, 10, 25), "To savings: swap")
    assert sent[-1] == ("POST", "https://api.nessieisreal.com/accounts/acct/transfers", {
        "transaction_date": "2026-10-25", "status": "completed", "amount": 7, "description": "To savings: swap"})
    nessie_service.create_account("cust", "Catch savings", 0, "Savings")
    assert sent[-1][2]["type"] == "Savings"


@pytest.mark.parametrize("day, today, due", [
    (28, date(2026, 10, 25), date(2026, 10, 28)), (25, date(2026, 10, 25), date(2026, 10, 25)),
    (1, date(2026, 10, 25), date(2026, 11, 1)), (15, date(2026, 12, 31), date(2027, 1, 15)),
    (28, date(2027, 1, 31), date(2027, 2, 28)),
])
def test_next_due_date(day, today, due):
    assert next_due_date(day, today) == due


def test_next_due_date_rejects_days_missing_from_some_months():
    for day in [0, 29, 31]:
        with pytest.raises(ValueError):
            next_due_date(day, date(2026, 10, 1))


@pytest.mark.parametrize("value, category", [
    ("Groceries", "groceries"), ("Supermarket", "groceries"), ("Dining", "restaurant"), ("Coffee Shop", "restaurant"),
    ("Health", "health"), ("Pharmacy", "health"), ("Gas", "transportation"), ("Household", "household"),
    (["Department Store", "Retail"], "household"), ("Jewelry", "other"), (None, "other"), (42, "other"),
])
def test_spending_category_maps_merchant_categories(value, category):
    assert nessie_service.spending_category(value) == category


def test_merchant_category_is_cached_and_falls_back_to_other(monkeypatch):
    lookups = []

    def fake_request(method, url, params=None, json=None, timeout=None):
        lookups.append(url)
        request = httpx.Request(method, url)
        if url.endswith("/missing"):
            return httpx.Response(404, text='"Merchant id does not exist"', request=request)
        return httpx.Response(200, json={"_id": "m1", "name": "H-E-B", "category": "Groceries"}, request=request)

    monkeypatch.setattr(nessie_service.httpx, "request", fake_request)
    assert nessie_service.merchant_category("m1") == "groceries"
    assert nessie_service.merchant_category("m1") == "groceries"
    assert nessie_service.merchant_category("missing") == "other"
    assert nessie_service.merchant_category(None) == "other"
    assert lookups == ["https://api.nessieisreal.com/merchants/m1", "https://api.nessieisreal.com/merchants/missing"]


def test_normalize_bill():
    bill = {"_id": "b1", "status": "recurring", "payee": "Austin Energy", "nickname": "Electric",
            "payment_amount": 68.4, "upcoming_payment_date": "2026-11-15", "payment_date": "2026-10-15"}
    row = nessie_service.normalize_bill(bill)
    assert (row["id"], row["type"], row["category"], row["description"]) == ("b1", "bill", "bill", "Austin Energy")
    assert row["date"] == date(2026, 11, 15) and row["amount"] == Decimal("68.4")
    for status in ["completed", "cancelled"]:
        assert nessie_service.normalize_bill({**bill, "status": status}) is None
    assert nessie_service.normalize_bill({**bill, "payment_amount": 0}) is None
    assert nessie_service.normalize_bill({**bill, "upcoming_payment_date": None, "payment_date": "soon"}) is None


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
