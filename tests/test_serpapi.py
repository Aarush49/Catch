"""Google Shopping result parsing: the extra listing details come from the same search, at no extra cost."""

import pytest

from backend.services.serpapi_service import _normalize_product

BASE = {"title": "Tide PODS Free & Gentle", "price": "$12.97", "extracted_price": 12.97,
        "product_link": "https://www.google.com/shopping/product/1", "source": "Walmart"}


def test_sale_reviews_delivery_tag_and_nearby_are_kept():
    product = _normalize_product({**BASE, "old_price": "$20", "extracted_old_price": 20, "reviews": 2700, "rating": 4.8,
                                  "delivery": "Delivery within 1h $20", "tag": "34% OFF",
                                  "extensions": ["Nearby, 8 mi", "34% OFF"]})
    assert (product.old_price, product.unit_price, product.reviews, product.rating) == (20.0, None, 2700, 4.8)
    assert (product.tag, product.delivery, product.nearby) == ("34% OFF", "Delivery within 1h $20", "Nearby, 8 mi")


@pytest.mark.parametrize("old_price, expected_old, expected_unit", [
    ("Usually $37", 37.0, None),
    ("$0.31/ct", None, "$0.31/ct"),       # a unit price, not a previous price
    ("$0.41/oz", None, "$0.41/oz"),
    ("$10", None, None),                  # not higher than the current price, so not a sale
    ("€20", None, None),
    ("", None, None),
])
def test_old_price_is_a_sale_only_when_it_is_a_higher_dollar_price(old_price, expected_old, expected_unit):
    product = _normalize_product({**BASE, "old_price": old_price})
    assert (product.old_price, product.unit_price) == (expected_old, expected_unit)


def test_missing_or_malformed_extras_are_ignored():
    product = _normalize_product({**BASE, "reviews": "lots", "extensions": "Nearby", "delivery": "  ", "tag": 5})
    assert (product.reviews, product.nearby, product.delivery, product.tag, product.old_price) == (None, None, None, None, None)
    assert _normalize_product({**BASE, "extensions": ["Also nearby"], "reviews": True}).nearby == "Also nearby"
