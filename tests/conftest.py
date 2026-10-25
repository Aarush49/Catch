import json
import time
from collections import namedtuple
from copy import deepcopy
from unittest.mock import Mock
from uuid import uuid4

import httpx
import jwt
import pytest

from app import database

_REAL_HTTP_CLIENT = httpx.Client
TEST_URL = "https://ripple-test.supabase.co"
TEST_JWT_SECRET = "test-jwt-secret-never-real-0123456789abcdef"

Call = namedtuple("Call", "method name params body")


def make_token(user_id: str, **overrides) -> str:
    claims = {
        "sub": user_id, "email": "person@example.com", "aud": "authenticated", "role": "authenticated",
        "iss": f"{TEST_URL}/auth/v1", "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return jwt.encode({key: value for key, value in claims.items() if value is not None}, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def user_id():
    return str(uuid4())


@pytest.fixture
def auth_headers(user_id):
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture(autouse=True)
def supabase_mock(monkeypatch):
    """Use the real SDK with mock HTTPS; never send local credentials or traffic."""
    monkeypatch.setenv("SUPABASE_URL", TEST_URL)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test_key_never_real")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
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
        assert http_request.url.path.startswith("/rest/v1/")
        name = http_request.url.path.removeprefix("/rest/v1/")
        body = json.loads(http_request.content) if http_request.content else None
        call = Call(http_request.method, name, dict(http_request.url.params), body)
        stub.calls.append(call)
        if stub.failure is not None:
            raise stub.failure
        key = (http_request.method, name)
        if key in stub.responses:
            response = stub.responses[key]
            data = response(call) if callable(response) else deepcopy(response)
        elif key == ("POST", "rpc/ripple_schema_version"):
            data = database.SCHEMA_VERSION
        elif http_request.method == "POST":
            rows = body if isinstance(body, list) else [body]
            data = [{"id": str(uuid4()), "completed": False, **row} for row in rows]
        elif http_request.method in {"GET", "DELETE"}:
            data = []
        else:
            raise AssertionError(f"Unexpected Supabase request: {key}")
        return httpx.Response(stub.status, text=json.dumps(data), headers={"content-type": "application/json"})

    def http_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        result = _REAL_HTTP_CLIENT(*args, **kwargs)
        stub.transports.append(result)
        return result
    monkeypatch.setattr(database.httpx, "Client", http_client)
    return stub


@pytest.fixture(autouse=True)
def no_real_gemini(monkeypatch):
    """Gemini clients must be faked; never send the local API key or traffic."""
    from backend.services import gemini_service

    def unexpected(*args, **kwargs):
        raise AssertionError("Unmocked Gemini client")
    monkeypatch.setattr(gemini_service.genai, "Client", unexpected)
    gemini_service._explanations.clear()
    monkeypatch.setattr(gemini_service, "_explanations_paused_until", 0.0)


@pytest.fixture(autouse=True)
def no_real_nessie(monkeypatch):
    """Nessie calls must be mocked; never send the local sandbox key or traffic."""
    from backend.services import nessie_service

    def unexpected(method, url, **kwargs):
        raise AssertionError(f"Unmocked Nessie request: {method} {httpx.URL(url).path}")
    monkeypatch.setenv("NESSIE_API_KEY", "fake-nessie-key")
    monkeypatch.setattr(nessie_service.httpx, "request", unexpected)
    nessie_service._merchant_categories.clear()
