from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import ParsedReceipt


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setattr(main, "parse_receipt", Mock(side_effect=AssertionError("Unexpected Gemini call")))
    monkeypatch.setattr(main, "NessieClient", Mock(side_effect=AssertionError("Unexpected Nessie call")))
    with TestClient(main.app) as test_client:
        yield test_client


def test_mock_receipt_scan_retains_original_response_fields(client):
    response = client.post("/receipts/scan", files={"file": ("receipt.png", b"test image", "image/png")})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"id", "store_name", "purchase_date", "subtotal", "tax", "total", "raw_json", "created_at", "items", "warnings"}
    assert data["store_name"] == "Demo Market"
    assert Decimal(str(data["total"])) == Decimal("14.02")
    assert data["items"][0]["full_name"] == "Organic Boneless Chicken Breast"
    assert data["items"][0]["receipt_id"] == data["id"]
    assert data["warnings"] == ["MOCK_MODE is enabled; this is sample receipt data."]


def test_gemini_parse_result_is_saved_without_changing_parser(client, monkeypatch, receipt_data):
    monkeypatch.setenv("MOCK_MODE", "false")
    parse = Mock(return_value=ParsedReceipt.model_validate(receipt_data))
    monkeypatch.setattr(main, "parse_receipt", parse)
    response = client.post("/receipts/scan", files={"file": ("receipt.jpg", b"jpeg bytes", "image/jpeg")})
    assert response.status_code == 200
    parse.assert_called_once_with(b"jpeg bytes", "image/jpeg")
    assert response.json()["warnings"] == receipt_data["warnings"]


def test_receipt_history_and_detail(client, supabase_mock, saved_receipt):
    supabase_mock.responses["ripple_receipts"] = [saved_receipt]
    history = client.get("/receipts")
    assert history.status_code == 200
    assert history.json()[0]["id"] == saved_receipt["id"]
    detail = client.get(f"/receipts/{saved_receipt['id']}")
    assert detail.status_code == 200
    assert detail.json() == history.json()[0]


def test_missing_receipt_is_404(client):
    assert client.get(f"/receipts/{uuid4()}").status_code == 404
    assert client.get("/receipts/not-a-uuid").status_code == 422


def test_items_and_spending_summary(client, supabase_mock, saved_receipt):
    supabase_mock.responses["ripple_items"] = saved_receipt["items"]
    response = client.get("/items", params={"category": "meat_seafood", "start": "2026-10-01", "end": "2026-10-24"})
    assert response.status_code == 200
    assert response.json()[0]["full_name"] == saved_receipt["items"][0]["full_name"]
    supabase_mock.responses["ripple_spending_summary"] = {
        "period": "all", "by_category": [{"category": "meat_seafood", "total": "12.98"}],
        "by_day": [{"day": "2026-10-24", "total": "12.98"}],
    }
    response = client.get("/spending/summary?period=all")
    assert response.status_code == 200
    assert response.json()["period"] == "all"
    assert Decimal(str(response.json()["by_category"][0]["total"])) == Decimal("12.98")


@pytest.mark.parametrize("url", ["/items?start=2026-10-25&end=2026-10-01", "/spending/summary?period=year"])
def test_existing_query_validation(client, supabase_mock, url):
    assert client.get(url).status_code == 422
    assert not supabase_mock.calls


@pytest.mark.parametrize("method, path", [("get", "/receipts"), ("get", "/items"), ("get", "/spending/summary"), ("post", "/receipts/scan")])
def test_database_outage_returns_safe_503(client, supabase_mock, method, path):
    supabase_mock.failure = httpx.ConnectError("sb_secret_test_key_never_real private-host")
    kwargs = {"files": {"file": ("receipt.png", b"image", "image/png")}} if method == "post" else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 503
    assert "sb_secret_test_key_never_real" not in response.text
    assert "private-host" not in response.text


def test_missing_database_configuration_returns_503(client, monkeypatch, supabase_mock):
    monkeypatch.delenv("SUPABASE_URL")
    response = client.get("/receipts")
    assert response.status_code == 503
    assert "SUPABASE_URL" in response.json()["detail"]
    assert not supabase_mock.calls


def test_invalid_item_from_parser_returns_422(client, monkeypatch, receipt_data, supabase_mock):
    monkeypatch.setenv("MOCK_MODE", "false")
    receipt_data["items"][0]["quantity"] = Decimal("0")
    monkeypatch.setattr(main, "parse_receipt", Mock(return_value=ParsedReceipt.model_validate(receipt_data)))
    response = client.post("/receipts/scan", files={"file": ("receipt.png", b"image", "image/png")})
    assert response.status_code == 422
    assert not supabase_mock.calls


def test_nessie_setup_reuses_persisted_ids(client, supabase_mock):
    supabase_mock.responses["ripple_demo_ids"] = {"customer_id": "customer-1", "account_id": "account-1"}
    response = client.post("/nessie/setup")
    assert response.status_code == 200
    assert response.json() == {"customer_id": "customer-1", "account_id": "account-1", "status": "reused"}
    main.NessieClient.assert_not_called()


def test_nessie_setup_saves_demo_ids(client, monkeypatch, supabase_mock):
    nessie = Mock()
    nessie.get_customers.return_value = [{"_id": "customer-1", "first_name": "Ripple", "last_name": "Demo"}]
    nessie.get_accounts.return_value = [{"_id": "account-1", "nickname": "Ripple Demo Checking"}]
    monkeypatch.setattr(main, "NessieClient", Mock(return_value=nessie))
    response = client.post("/nessie/setup")
    assert response.status_code == 200
    assert response.json()["account_id"] == "account-1"
    assert supabase_mock.calls[-1] == ("ripple_demo_ids", {"p_customer_id": "customer-1", "p_account_id": "account-1"})


def test_health_does_not_require_database(client, monkeypatch, supabase_mock):
    monkeypatch.delenv("SUPABASE_URL")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not supabase_mock.calls
