import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_alternatives_endpoint(client, respond, listing):
    respond({"shopping_results": [listing()]})
    response = client.get("/api/shopping/alternatives", params={
        "query": "Acme Widget", "original_price": 30, "brand": "Acme",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "Acme Widget"
    assert body["original_price"] == 30
    assert body["currency"] == "USD"
    assert body["alternatives"][0]["potential_savings"] == 10.01
    assert body["alternatives"][0]["potential_savings_percent"] == 33.37
    assert body["alternatives"][0]["match_type"] == "exact_title_match"
    assert "Shipping and taxes" in body["savings_note"]
    assert "test-key-never-real" not in response.text


def test_empty_alternatives_are_a_success(client):
    response = client.get("/api/shopping/alternatives", params={"query": "Widget", "original_price": 100})
    assert response.status_code == 200
    assert response.json()["alternatives"] == []


@pytest.mark.parametrize("params", [
    {}, {"query": "Widget"}, {"original_price": 100},
    {"query": "Widget", "original_price": "bad"},
    {"query": "Widget", "original_price": 0},
    {"query": "Widget", "original_price": -1},
    {"query": "Widget", "original_price": "nan"},
    {"query": "Widget", "original_price": "inf"},
    {"query": "", "original_price": 100},
    {"query": "  ", "original_price": 100},
    {"query": "!!!", "original_price": 100},
    {"query": "a" * 201, "original_price": 100},
    {"query": "Widget", "original_price": 100, "brand": " "},
])
def test_invalid_request_is_rejected_without_search(client, serpapi_request, params):
    response = client.get("/api/shopping/alternatives", params=params)
    assert response.status_code == 422
    serpapi_request.assert_not_called()


def test_missing_credentials_status(client, monkeypatch, serpapi_request):
    monkeypatch.delenv("SERPAPI_KEY")
    response = client.get("/api/shopping/alternatives", params={"query": "Widget", "original_price": 100})
    assert response.status_code == 503
    serpapi_request.assert_not_called()


@pytest.mark.parametrize("upstream, expected", [(401, 503), (429, 503), (500, 502)])
def test_provider_failure_status_and_redaction(client, respond, upstream, expected):
    respond({"error": "test-key-never-real"}, upstream)
    response = client.get("/api/shopping/alternatives", params={"query": "Widget", "original_price": 100})
    assert response.status_code == expected
    assert "test-key-never-real" not in response.text


def test_timeout_status_and_redaction(client, serpapi_request):
    serpapi_request.side_effect = httpx.ReadTimeout("https://serpapi.com/?api_key=test-key-never-real")
    response = client.get("/api/shopping/alternatives", params={"query": "Widget", "original_price": 100})
    assert response.status_code == 504
    assert "test-key-never-real" not in response.text


def test_malformed_provider_response_status(client, respond):
    respond({"shopping_results": {}})
    response = client.get("/api/shopping/alternatives", params={"query": "Widget", "original_price": 100})
    assert response.status_code == 502


def test_existing_health_endpoint(client, serpapi_request):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    serpapi_request.assert_not_called()


def test_shopping_response_is_in_openapi(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/shopping/alternatives"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ShoppingAlternativesResponse"
    }
