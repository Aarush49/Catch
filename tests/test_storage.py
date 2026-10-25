from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import httpx

from app import storage
from app.database import DatabaseConstraintError, DatabaseError


def test_create_and_retrieve_user(supabase_mock, user):
    first = storage.get_or_create_user("ripple-demo")
    assert storage.get_or_create_user("ripple-demo") == first
    supabase_mock.responses["ripple_get_user"] = user
    assert storage.get_user(first["id"]) == first
    assert isinstance(first["id"], UUID)
    assert isinstance(first["created_at"], datetime)


def test_user_input_is_sent_as_rpc_parameters(supabase_mock):
    username = "test'; DROP TABLE users; --"
    storage.get_or_create_user(username)
    assert supabase_mock.calls == [("ripple_get_or_create_user", {"p_username": username})]


@pytest.mark.parametrize("username", [None, "", " ", "x" * 101])
def test_invalid_username_does_not_request(supabase_mock, username):
    with pytest.raises(ValueError):
        storage.get_or_create_user(username)
    assert not supabase_mock.calls


def test_missing_user():
    assert storage.get_user(uuid4()) is None


def test_save_receipt_preserves_contract_and_is_one_atomic_rpc(supabase_mock, receipt_data):
    result = storage.save_receipt(receipt_data)
    assert set(result) == {"id", "store_name", "purchase_date", "subtotal", "tax", "total", "raw_json", "created_at", "items", "warnings"}
    assert result["raw_json"] == receipt_data
    assert result["total"] == Decimal("14.02")
    assert isinstance(result["id"], UUID)
    assert result["items"][0]["receipt_id"] == result["id"]
    assert result["items"][0]["purchased_at"] == datetime(2026, 10, 24, tzinfo=timezone.utc)
    assert result["warnings"] == receipt_data["warnings"]
    assert len(supabase_mock.calls) == 1
    name, params = supabase_mock.calls[0]
    assert name == "ripple_save_receipt"
    assert params["p_user_id"] is None
    assert params["p_receipt"]["total"] == "14.02"


def test_explicit_user_and_high_precision_money(supabase_mock, receipt_data):
    owner = uuid4()
    amount = Decimal("12345678901234567890.123456789")
    receipt_data["total"] = amount
    receipt_data["items"][0]["unit_price"] = amount
    result = storage.save_receipt(receipt_data, owner)
    assert result["total"] == result["items"][0]["unit_price"] == amount
    assert supabase_mock.calls[0][1]["p_user_id"] == str(owner)
    assert supabase_mock.calls[0][1]["p_receipt"]["total"] == str(amount)


def test_optional_null_fields_empty_items():
    result = storage.save_receipt({"total": "0", "items": []})
    assert result["store_name"] is result["purchase_date"] is result["subtotal"] is result["tax"] is None
    assert result["items"] == result["warnings"] == []


def test_missing_purchase_date_preserves_local_fallback(supabase_mock, receipt_data):
    receipt_data["purchase_date"] = None
    result = storage.save_receipt(receipt_data)
    assert result["purchase_date"] is None
    assert result["items"][0]["purchased_at"].date() == date.today()
    assert supabase_mock.calls[0][1]["p_fallback_date"] == date.today().isoformat()


def test_rpc_constraint_failure_is_sanitized_without_partial_client_writes(supabase_mock, receipt_data):
    supabase_mock.status = 400
    supabase_mock.responses["ripple_save_receipt"] = {"code": "23503", "message": "sb_secret_test_key_never_real", "details": None, "hint": None}
    with pytest.raises(DatabaseConstraintError):
        storage.save_receipt(receipt_data, uuid4())
    assert len(supabase_mock.calls) == 1
    assert supabase_mock.calls[0][0] == "ripple_save_receipt"


def test_receipt_timeout_is_not_retried(supabase_mock, receipt_data):
    supabase_mock.failure = httpx.ReadTimeout("sb_secret_test_key_never_real")
    with pytest.raises(DatabaseError):
        storage.save_receipt(receipt_data)
    assert len(supabase_mock.calls) == 1


@pytest.mark.parametrize("field, value", [("total", "-1"), ("tax", "-1"), ("total", "NaN"), ("total", "Infinity"), ("purchase_date", "2026-13-01"), ("items", None)])
def test_invalid_receipt_does_not_request(supabase_mock, receipt_data, field, value):
    receipt_data[field] = value
    with pytest.raises(storage.InvalidReceiptError):
        storage.save_receipt(receipt_data)
    assert not supabase_mock.calls


@pytest.mark.parametrize("field, value", [
    ("raw_name", " "), ("full_name", ""), ("category", "unknown"),
    ("quantity", "0"), ("quantity", "-1"), ("quantity", "NaN"),
    ("unit_price", "-0.01"), ("total_price", "-0.01"), ("total_price", "Infinity"),
])
def test_invalid_item_does_not_request(supabase_mock, receipt_data, field, value):
    receipt_data["items"][0][field] = value
    with pytest.raises(storage.InvalidReceiptError):
        storage.save_receipt(receipt_data)
    assert not supabase_mock.calls


def test_receipt_history_and_owner_parameters(supabase_mock, saved_receipt):
    owner = uuid4()
    supabase_mock.responses["ripple_receipts"] = [saved_receipt]
    result = storage.list_receipts(owner)
    assert result[0]["id"] == UUID(saved_receipt["id"])
    assert result[0]["raw_json"]["purchase_date"] == date(2026, 10, 24)
    assert result[0]["raw_json"]["total"] == Decimal("14.02")
    assert supabase_mock.calls[-1] == ("ripple_receipts", {"p_user_id": str(owner)})
    assert storage.get_receipt(UUID(saved_receipt["id"]), owner) == result[0]
    assert supabase_mock.calls[-1][1]["p_receipt_id"] == saved_receipt["id"]
    assert storage.list_receipt_items(UUID(saved_receipt["id"]), owner) == result[0]["items"]


def test_empty_collections_and_missing_receipt():
    assert storage.list_receipts() == []
    assert storage.get_receipt(uuid4()) is None
    assert storage.list_receipt_items(uuid4()) == []
    assert storage.list_items(None, None, None) == []
    assert storage.spending_summary("all") == {"period": "all", "by_category": [], "by_day": []}


def test_item_filters_are_literal_parameters(supabase_mock, saved_receipt):
    supabase_mock.responses["ripple_items"] = saved_receipt["items"]
    category = "produce'; DROP TABLE receipt_items; --"
    owner = uuid4()
    result = storage.list_items(category, date(2026, 10, 1), date.max, owner)
    assert len(result) == 1
    assert supabase_mock.calls[-1] == ("ripple_items", {
        "p_category": category, "p_start": "2026-10-01", "p_end": "9999-12-31", "p_user_id": str(owner),
    })


@pytest.mark.parametrize("period", ["week", "month", "all"])
def test_spending_summary_returns_exact_decimal_aggregates(supabase_mock, period):
    amount = "12345678901234567890.123456789"
    supabase_mock.responses["ripple_spending_summary"] = {
        "period": period, "by_category": [{"category": "produce", "total": amount}],
        "by_day": [{"day": "2026-10-24", "total": amount}],
    }
    result = storage.spending_summary(period)
    assert result["by_category"][0]["total"] == Decimal(amount)
    assert result["by_day"][0] == {"day": date(2026, 10, 24), "total": Decimal(amount)}


def test_demo_ids_persist_and_keep_tuple_interface(supabase_mock):
    assert storage.get_demo_ids() is None
    storage.set_demo_ids("customer-1", "account-1")
    assert supabase_mock.calls[-1] == ("ripple_demo_ids", {"p_customer_id": "customer-1", "p_account_id": "account-1"})
    supabase_mock.responses["ripple_demo_ids"] = {"customer_id": "customer-1", "account_id": "account-1"}
    assert storage.get_demo_ids() == ("customer-1", "account-1")


@pytest.mark.parametrize("payload", [None, {}, [None], [{"id": "bad"}]])
def test_malformed_read_response_is_safe(supabase_mock, payload):
    supabase_mock.responses["ripple_receipts"] = payload
    with pytest.raises(DatabaseError):
        storage.list_receipts()


def test_numeric_json_float_is_rejected_to_prevent_precision_loss(supabase_mock, saved_receipt):
    saved_receipt["total"] = 14.02
    supabase_mock.responses["ripple_receipts"] = [saved_receipt]
    with pytest.raises(DatabaseError):
        storage.list_receipts()
