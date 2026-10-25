import time
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import main
from backend.services import supabase_jwt
from tests.conftest import TEST_URL, make_token

SCANNED = {
    "merchant": "H-E-B", "purchased_at": "2026-10-24", "currency": "USD",
    "items": [{"name": "Oat milk", "quantity": 1, "price": 4.19, "category": "Groceries"}],
    "subtotal": 4.19, "tax": 0.35, "total": 4.54, "needs_review": False, "review_reason": None,
}
IMAGE = {"file": ("receipt.jpg", b"jpeg bytes", "image/jpeg")}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-never-real")
    monkeypatch.setattr(main, "scan_image", Mock(return_value=SCANNED))
    with TestClient(main.app) as test_client:
        yield test_client


def test_health_does_not_require_database(client, monkeypatch, supabase_mock):
    monkeypatch.delenv("SUPABASE_URL")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not supabase_mock.calls


def test_scan_returns_parsed_receipt_without_saving(client, supabase_mock, auth_headers):
    response = client.post("/receipts/scan", files=IMAGE, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == SCANNED
    main.scan_image.assert_called_once_with(b"jpeg bytes", "image/jpeg")
    assert not supabase_mock.calls


@pytest.mark.parametrize("token", [
    None, "not-a-jwt",
    make_token("user-1", exp=int(time.time()) - 10),
    make_token("user-1", iss="https://someone-else.supabase.co/auth/v1"),
    make_token("user-1", aud="anon"),
    make_token("user-1", sub=None),
    jwt.encode({"sub": "user-1", "aud": "authenticated", "iss": f"{TEST_URL}/auth/v1", "exp": int(time.time()) + 60},
               "a-different-secret-that-is-long-enough", algorithm="HS256"),
])
def test_scan_rejects_missing_or_invalid_sessions(client, token):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.post("/receipts/scan", files=IMAGE, headers=headers)
    assert response.status_code == 401
    main.scan_image.assert_not_called()


def test_scan_verifies_asymmetric_tokens_from_the_project_jwks(client, monkeypatch, user_id):
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    private_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode({"sub": user_id, "aud": "authenticated", "iss": f"{TEST_URL}/auth/v1",
                        "exp": int(time.time()) + 60}, private_key, algorithm="ES256")
    jwks = Mock()
    jwks.get_signing_key_from_jwt.return_value = Mock(key=private_key.public_key())
    requested = []
    monkeypatch.setattr(supabase_jwt, "_jwks_client", lambda url: requested.append(url) or jwks)
    response = client.post("/receipts/scan", files=IMAGE, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert requested == [f"{TEST_URL}/auth/v1/.well-known/jwks.json"]


@pytest.mark.parametrize("files, status", [
    ({"file": ("receipt.gif", b"gif", "image/gif")}, 400),
    ({"file": ("receipt.jpg", b"", "image/jpeg")}, 400),
    ({"file": ("receipt.jpg", b"x" * (main.MAX_IMAGE_BYTES + 1), "image/jpeg")}, 413),
])
def test_scan_validates_uploads(client, auth_headers, files, status):
    assert client.post("/receipts/scan", files=files, headers=auth_headers).status_code == status
    main.scan_image.assert_not_called()


def test_scan_without_gemini_key_is_503(client, monkeypatch, auth_headers):
    monkeypatch.delenv("GEMINI_API_KEY")
    response = client.post("/receipts/scan", files=IMAGE, headers=auth_headers)
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_unreadable_receipt_is_422(client, auth_headers):
    main.scan_image.side_effect = ValueError("The image does not appear to contain a readable receipt.")
    response = client.post("/receipts/scan", files=IMAGE, headers=auth_headers)
    assert response.status_code == 422
    assert "readable receipt" in response.json()["detail"]


def test_retired_routes_are_gone(client):
    paths = client.get("/openapi.json").json()["paths"]
    for retired in ["/receipts", "/items", "/spending/summary", "/nessie/setup", "/api/auth/login", "/api/receipts"]:
        assert retired not in paths
    for kept in ["/health", "/receipts/scan", "/api/shopping/alternatives", "/api/shopping-list/items",
                 "/api/nessie/transactions", "/api/spending/history", "/api/predictions"]:
        assert kept in paths


def test_backend_entry_point_is_the_same_app():
    from backend.main import app
    assert app is main.app
