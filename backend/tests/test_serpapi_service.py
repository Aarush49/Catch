import httpx
import pytest

from backend.services.serpapi_service import (
    REQUEST_TIMEOUT_SECONDS,
    SERPAPI_URL,
    ShoppingServiceError,
    find_alternatives,
    search_products,
)


def test_successful_search_normalizes_products(respond, listing, serpapi_request):
    respond({"shopping_results": [listing()]})

    products = search_products("Acme Widget")

    assert [product.model_dump() for product in products] == [{
        "title": "Acme Widget",
        "price": 19.99,
        "source": "Example Merchant",
        "rating": 4.5,
        "link": "https://example.com/products/widget",
        "thumbnail": "https://example.com/widget.jpg",
        "product_id": "12345",
        "reviews": None,
        "old_price": None,
        "unit_price": None,
        "tag": None,
        "delivery": None,
        "nearby": None,
    }]
    serpapi_request.assert_called_once_with(
        SERPAPI_URL,
        params={
            "engine": "google_shopping",
            "q": "Acme Widget",
            "api_key": "test-key-never-real",
            "gl": "us",
            "hl": "en",
            "location": "United States",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_does_not_make_a_request(monkeypatch, serpapi_request, key):
    if key is None:
        monkeypatch.delenv("SERPAPI_KEY")
    else:
        monkeypatch.setenv("SERPAPI_KEY", key)
    with pytest.raises(ShoppingServiceError, match="not configured") as error:
        search_products("Acme Widget")
    assert error.value.status_code == 503
    serpapi_request.assert_not_called()


@pytest.mark.parametrize("payload", [
    {"shopping_results": []},
    {"search_metadata": {"status": "Success"}},
])
def test_empty_results(respond, payload):
    respond(payload)
    assert search_products("Acme Widget") == []


@pytest.mark.parametrize("price", [None, 0, -10, True, float("nan"), float("inf"), "bad"])
def test_invalid_or_missing_prices_are_skipped(respond, listing, price):
    item = listing(extracted_price=price)
    item.pop("price")
    respond({"shopping_results": [item]})
    assert search_products("Acme Widget") == []


@pytest.mark.parametrize("price", [
    "€19.99", "CA$19.99", "A$19.99", "$19.99 / month", "from $19.99",
    "$19.99–$29.99", "", "$1,99", "$-19.99", "$0.00", "NaN", 19.99,
])
def test_ambiguous_or_non_usd_prices_are_skipped(respond, listing, price):
    respond({"shopping_results": [listing(price=price)]})
    assert search_products("Acme Widget") == []


@pytest.mark.parametrize("displayed, expected", [
    ("$1,234.50", 1234.50), ("US$19.99", 19.99), ("USD 19.99", 19.99),
    ("19.99 USD", 19.99), ("19.99", 19.99),
])
def test_formatted_price_fallback(respond, listing, displayed, expected):
    respond({"shopping_results": [listing(price=displayed, extracted_price=None)]})
    assert search_products("Acme Widget")[0].price == expected


def test_numeric_only_price_uses_us_search_locale(respond, listing):
    respond({"shopping_results": [listing(price=None)]})
    assert search_products("Acme Widget")[0].price == 19.99


def test_conflicting_price_fields_are_skipped(respond, listing):
    respond({"shopping_results": [listing(price="$99.99")]})
    assert search_products("Acme Widget") == []


@pytest.mark.parametrize("overrides", [
    {"title": None}, {"title": " "}, {"title": []},
    {"product_link": None}, {"product_link": "javascript:alert(1)"},
    {"product_link": "https://user:password@example.com"},
    {"installment": {"price": "$19.99/mo"}},
    {"second_hand_condition": "refurbished"},
])
def test_invalid_or_incomparable_listings_are_skipped(respond, listing, overrides):
    respond({"shopping_results": [None, "bad", {}, listing(**overrides)]})
    assert search_products("Acme Widget") == []


def test_optional_missing_fields_are_not_fabricated(respond, listing):
    respond({"shopping_results": [listing(source=None, rating=None, thumbnail=None, product_id=None)]})
    product = search_products("Acme Widget")[0]
    assert product.source is product.rating is product.thumbnail is product.product_id is None


@pytest.mark.parametrize("rating", [float("nan"), float("inf"), -1, 6, 10**400, True, "4.5", {}])
def test_invalid_rating_is_omitted(respond, listing, rating):
    respond({"shopping_results": [listing(rating=rating, product_id=123)]})
    product = search_products("Acme Widget")[0]
    assert product.rating is None
    assert product.product_id == "123"


def test_merchant_link_is_preferred_over_google_product_link(respond, listing):
    respond({"shopping_results": [listing(link="https://merchant.example/widget")]})
    assert search_products("Acme Widget")[0].link == "https://merchant.example/widget"


@pytest.mark.parametrize("payload", [
    None, [], {}, {"shopping_results": None}, {"shopping_results": {}},
    {"shopping_results": "bad"}, {"error": "test-key-never-real: upstream failure"},
    {"search_metadata": {"status": "Error"}, "shopping_results": []},
])
def test_invalid_responses_and_provider_errors_are_sanitized(respond, payload):
    respond(payload)
    with pytest.raises(ShoppingServiceError) as error:
        search_products("Acme Widget")
    assert error.value.status_code == 502
    assert "test-key-never-real" not in str(error.value)


def test_non_json_response(serpapi_request):
    serpapi_request.return_value = httpx.Response(
        200, text="<html>test-key-never-real</html>",
        request=httpx.Request("GET", SERPAPI_URL),
    )
    with pytest.raises(ShoppingServiceError, match="invalid JSON"):
        search_products("Acme Widget")


@pytest.mark.parametrize("status, expected", [(400, 502), (401, 503), (403, 503), (429, 503), (500, 502)])
def test_http_failures(respond, status, expected):
    respond({"error": "test-key-never-real"}, status)
    with pytest.raises(ShoppingServiceError) as error:
        search_products("Acme Widget")
    assert error.value.status_code == expected
    assert "test-key-never-real" not in str(error.value)


@pytest.mark.parametrize("failure, expected", [
    (httpx.ReadTimeout("test-key-never-real"), 504),
    (httpx.ConnectError("test-key-never-real"), 502),
])
def test_network_errors(serpapi_request, failure, expected):
    serpapi_request.side_effect = failure
    with pytest.raises(ShoppingServiceError) as error:
        search_products("Acme Widget")
    assert error.value.status_code == expected
    assert "test-key-never-real" not in str(error.value)


def test_comparison_filters_sorts_and_limits_to_three(respond, listing):
    prices = [120, 100, 95, 90, 85, 80, 75]
    respond({"shopping_results": [
        listing(price=f"${price}.00", extracted_price=price, source=f"Store {price}")
        for price in prices
    ]})
    alternatives = find_alternatives("Acme Widget", 100)
    assert [item.price for item in alternatives] == [75, 80, 85]
    assert [item.potential_savings for item in alternatives] == [25, 20, 15]
    assert [item.potential_savings_percent for item in alternatives] == [25, 20, 15]


def test_savings_use_decimal_arithmetic(respond, listing):
    respond({"shopping_results": [listing(price="$0.10", extracted_price=0.10)]})
    alternative = find_alternatives("Acme Widget", 0.30)[0]
    assert alternative.potential_savings == 0.20
    assert alternative.potential_savings_percent == 66.67


def test_original_price_is_not_rounded_before_comparison(respond, listing):
    respond({"shopping_results": [listing(price="$19.99")]})
    assert find_alternatives("Acme Widget", 19.989) == []
    assert find_alternatives("Acme Widget", 19.991) == []  # Less than one rounded cent.


def test_percentage_uses_unrounded_difference(respond, listing):
    respond({"shopping_results": [listing(price="$0.01", extracted_price=0.01)]})
    alternative = find_alternatives("Acme Widget", 0.015)[0]
    assert alternative.potential_savings == 0.01
    assert alternative.potential_savings_percent == 33.33


def test_matching_distinguishes_exact_titles_from_possible_variants(respond, listing):
    titles = ["NIKE Air Force 1", "Nike Air Force 1 Low White", "Nike Air Force 2", "Nike socks"]
    respond({"shopping_results": [
        listing(title=title, source=f"Store {index}") for index, title in enumerate(titles)
    ]})
    alternatives = find_alternatives("Nike Air Force 1", 120)
    assert {item.title: item.match_type for item in alternatives} == {
        "NIKE Air Force 1": "exact_title_match",
        "Nike Air Force 1 Low White": "similar_alternative",
    }
    assert all("unverified" in item.match_reason or "variant" in item.match_reason for item in alternatives)


def test_optional_brand_is_used_in_search_and_matching(respond, listing, serpapi_request):
    respond({"shopping_results": [listing(), listing(title="Other Widget")]})
    alternatives = find_alternatives("Widget", 100, brand="Acme")
    assert [item.title for item in alternatives] == ["Acme Widget"]
    assert alternatives[0].match_type == "exact_title_match"
    assert serpapi_request.call_args.kwargs["params"]["q"] == "Acme Widget"


def test_brand_is_not_duplicated_in_search(respond, listing, serpapi_request):
    respond({"shopping_results": [listing()]})
    find_alternatives("Acme Widget", 100, brand="acme")
    assert serpapi_request.call_args.kwargs["params"]["q"] == "Acme Widget"


@pytest.mark.parametrize("title", [
    "Acme Widget replacement case", "Case compatible with Acme Widget",
    "Acme Widget refurbished", "Acme Widget replica", "Acme Widget charger",
])
def test_accessories_and_condition_changes_are_excluded(respond, listing, title):
    respond({"shopping_results": [listing(title=title)]})
    assert find_alternatives("Acme Widget", 100) == []


def test_accessory_can_be_the_requested_product(respond, listing):
    respond({"shopping_results": [listing(title="Acme Widget case")]})
    assert len(find_alternatives("Acme Widget case", 100)) == 1


def test_model_numbers_and_capacities_must_match(respond, listing):
    respond({"shopping_results": [
        listing(title="Acme Phone 14 128GB"),
        listing(title="Acme Phone 15 128GB"),
        listing(title="Acme Phone 14 64GB"),
    ]})
    assert [item.title for item in find_alternatives("Acme Phone 14 128GB", 100)] == [
        "Acme Phone 14 128GB"
    ]


def test_duplicate_listings_do_not_fill_slots(respond, listing):
    respond({"shopping_results": [listing(), listing(), listing(source="Another Merchant")]})
    assert len(find_alternatives("Acme Widget", 100)) == 2


def test_no_cheaper_listings(respond, listing):
    respond({"shopping_results": [listing()]})
    assert find_alternatives("Acme Widget", 19.99) == []


@pytest.mark.parametrize("query, original", [(" ", 100), ("!!!", 100), ("Widget", 0), ("Widget", float("nan"))])
def test_invalid_comparison_input_does_not_search(serpapi_request, query, original):
    with pytest.raises(ValueError):
        find_alternatives(query, original)
    serpapi_request.assert_not_called()
