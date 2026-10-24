import json
from unittest.mock import Mock

import httpx
import pytest

from backend.services import serpapi_service


@pytest.fixture(autouse=True)
def serpapi_request(monkeypatch):
    """No test may use the network or a developer's real SerpAPI credentials."""
    monkeypatch.setenv("SERPAPI_KEY", "test-key-never-real")
    request = Mock(
        return_value=httpx.Response(
            200,
            json={"shopping_results": []},
            request=httpx.Request("GET", serpapi_service.SERPAPI_URL),
        )
    )
    monkeypatch.setattr(serpapi_service.httpx, "get", request)
    return request


@pytest.fixture
def respond(serpapi_request):
    def set_response(payload, status=200):
        serpapi_request.return_value = httpx.Response(
            status,
            # Include nonstandard NaN/Infinity to exercise malformed upstream
            # numbers; httpx's json= helper rejects these before tests run.
            text=json.dumps(payload, allow_nan=True),
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", serpapi_service.SERPAPI_URL),
        )
    return set_response


@pytest.fixture
def listing():
    def make_listing(**overrides):
        item = {
            "title": "Acme Widget",
            "price": "$19.99",
            "extracted_price": 19.99,
            "source": "Example Merchant",
            "rating": 4.5,
            "product_link": "https://example.com/products/widget",
            "thumbnail": "https://example.com/widget.jpg",
            "product_id": "12345",
        }
        item.update(overrides)
        return item
    return make_listing
