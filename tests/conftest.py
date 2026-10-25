import json
from copy import deepcopy
from datetime import date, datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from app import database
from app.models import ParsedReceipt

_REAL_HTTP_CLIENT = httpx.Client


def pytest_addoption(parser):
    parser.addoption("--run-db-integration", action="store_true", default=False)


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-db-integration"):
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(pytest.mark.skip(reason="Use --run-db-integration with TEST_SUPABASE_* settings."))


@pytest.fixture
def receipt_data():
    return ParsedReceipt.model_validate({
        "store_name": "Demo Market", "purchase_date": "2026-10-24",
        "subtotal": "12.98", "tax": "1.04", "total": "14.02",
        "items": [{
            "raw_name": "ORG BNLS CHKN BRST", "full_name": "Organic Boneless Chicken Breast",
            "category": "meat_seafood", "quantity": "1", "unit_price": "12.98", "total_price": "12.98",
        }], "warnings": ["Check the package size."],
    }).model_dump()


def receipt_response(receipt, fallback_date=None):
    """Construct fixture data in the RPC's JSON wire format, not a mock SQL DB."""
    raw = ParsedReceipt.model_validate(receipt).model_dump(mode="json")
    now = datetime.now(timezone.utc).isoformat()
    receipt_id = str(uuid4())
    purchased_at = (raw['purchase_date'] or fallback_date or date.today().isoformat()) + 'T00:00:00+00:00'
    return {
        "id": receipt_id, "store_name": raw["store_name"], "purchase_date": raw["purchase_date"],
        "subtotal": raw["subtotal"], "tax": raw["tax"], "total": raw["total"],
        "raw_json": raw, "created_at": now, "warnings": raw["warnings"],
        "items": [{"id": str(uuid4()), "receipt_id": receipt_id, **item,
                   "purchased_at": purchased_at, "created_at": now, "carbon_kg_co2e": str(original.get("carbon_kg_co2e", "0"))}
                  for item, original in zip(raw["items"], receipt["items"])],
    }


@pytest.fixture
def saved_receipt(receipt_data):
    return receipt_response(receipt_data)


@pytest.fixture
def user():
    return {"id": str(uuid4()), "username": "ripple-demo", "created_at": datetime.now(timezone.utc).isoformat()}


@pytest.fixture(autouse=True)
def supabase_mock(request, monkeypatch, user):
    """Use the real SDK with mock HTTPS; never send local credentials or traffic."""
    if request.node.get_closest_marker("integration"):
        return None
    monkeypatch.setenv("SUPABASE_URL", "https://ripple-test.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test_key_never_real")
    stub = Mock()
    stub.responses = {}
    stub.status = 200
    stub.failure = None
    stub.calls = []
    stub.transports = []

    def handle(http_request):
        assert http_request.url.scheme == "https"
        assert http_request.url.host == "ripple-test.supabase.co"
        assert http_request.headers["apikey"] == "sb_secret_test_key_never_real"
        assert http_request.url.path.startswith("/rest/v1/rpc/")
        name = http_request.url.path.rsplit("/", 1)[-1]
        params = json.loads(http_request.content)
        stub.calls.append((name, params))
        if stub.failure is not None:
            raise stub.failure
        if name in stub.responses:
            response = stub.responses[name]
            data = response(params) if callable(response) else deepcopy(response)
        elif name == "ripple_save_receipt":
            data = receipt_response(params["p_receipt"], params["p_fallback_date"])
        elif name in {"ripple_receipts", "ripple_items"}:
            data = []
        elif name == "ripple_spending_summary":
            data = {"period": params["p_period"], "by_category": [], "by_day": []}
        elif name == "ripple_get_or_create_user":
            data = {**user, "username": params["p_username"]}
        elif name == "ripple_get_user":
            data = None
        elif name == "ripple_demo_ids":
            data = {"customer_id": params["p_customer_id"], "account_id": params["p_account_id"]} if params else None
        elif name == "ripple_check":
            data = {"status": "ok", "schema_version": 2}
        else:
            raise AssertionError(f"Unexpected RPC: {name}")
        return httpx.Response(stub.status, text=json.dumps(data), headers={"content-type": "application/json"})

    def http_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        result = _REAL_HTTP_CLIENT(*args, **kwargs)
        stub.transports.append(result)
        return result
    monkeypatch.setattr(database.httpx, "Client", http_client)
    return stub
