"""Google Shopping search and conservative, title-based price comparisons."""

import math
import os
import re
import time
from threading import RLock
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from urllib.parse import urlsplit

import httpx

from backend.models import ShoppingAlternative, ShoppingProduct


SERPAPI_URL = "https://serpapi.com/search.json"
REQUEST_TIMEOUT_SECONDS = 15.0
CACHE_TTL_SECONDS = 15 * 60
MAX_CACHE_ENTRIES = 256
_CENT = Decimal("0.01")
_USD_PRICE = re.compile(
    r"(?:US\$|\$|USD\s*)?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?:\s*USD)?",
    re.IGNORECASE,
)
# Reject common accessories, imitation products, and condition changes unless
# those terms are part of the requested product itself.
_NON_COMPARABLE_TERMS = {
    "accessory", "accessories", "adapter", "band", "cable", "case", "charger",
    "compatible", "cover", "dupe", "insole", "insoles", "keychain", "lace",
    "laces", "mount", "poster", "preowned", "protector", "refurbished",
    "renewed", "replacement", "replica", "restored", "skin", "stand", "sticker",
    "strap", "used",
}
_cache_lock = RLock()
_product_cache: dict[tuple[str, object], tuple[float, list[ShoppingProduct]]] = {}


class ShoppingServiceError(Exception):
    """A safe public error; never include upstream bodies or request URLs."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _public_url(value: object) -> str | None:
    value = _text(value)
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not (
            parsed.username or parsed.password
        ):
            return value
    except ValueError:
        pass
    return None


def _positive_price(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        price = Decimal(str(value))
        # Only finite, positive cent prices that JSON can represent as floats.
        if not price.is_finite() or price <= 0 or not math.isfinite(float(price)):
            return None
        with localcontext() as context:
            context.prec = 340
            rounded = price.quantize(_CENT, rounding=ROUND_HALF_UP)
        return rounded if rounded > 0 else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def _listing_price(item: dict) -> Decimal | None:
    displayed = item.get("price")
    extracted = _positive_price(item.get("extracted_price"))
    if displayed is None:
        # The search is localized to the US; unlabeled numeric prices are
        # treated as USD. Never convert an explicitly foreign-currency price.
        return extracted
    if not isinstance(displayed, str):
        return None
    match = _USD_PRICE.fullmatch(displayed.strip())
    if not match:
        # Excludes foreign currencies, ranges, "from", and per-month prices.
        return None
    price = _positive_price(match.group(1).replace(",", ""))
    if extracted is not None and extracted != price:
        return None
    return price


def _normalize_product(item: object) -> ShoppingProduct | None:
    if not isinstance(item, dict) or item.get("installment") or item.get("second_hand_condition"):
        return None
    title = _text(item.get("title"))
    link = _public_url(item.get("link")) or _public_url(item.get("product_link"))
    price = _listing_price(item)
    if not title or not link or price is None:
        return None
    rating = item.get("rating")
    if (
        isinstance(rating, bool)
        or not isinstance(rating, (int, float))
        or not 0 <= rating <= 5
    ):
        rating = None
    product_id = item.get("product_id")
    if isinstance(product_id, int) and not isinstance(product_id, bool):
        product_id = str(product_id)
    reviews = item.get("reviews")
    if isinstance(reviews, bool) or not isinstance(reviews, int) or reviews < 0:
        reviews = None
    old_price, unit_price = _old_price(item, price)
    extensions = [text for value in item.get("extensions") or [] if (text := _text(value))] if isinstance(item.get("extensions"), list) else []
    return ShoppingProduct(
        title=title,
        price=float(price),
        source=_text(item.get("source")),
        rating=rating,
        link=link,
        thumbnail=_public_url(item.get("thumbnail")),
        product_id=_text(product_id),
        reviews=reviews,
        old_price=float(old_price) if old_price is not None else None,
        unit_price=unit_price,
        tag=_text(item.get("tag")),
        delivery=_text(item.get("delivery")),
        nearby=next((text for text in extensions if text.casefold().startswith(("nearby", "also nearby"))), None),
    )


_UNIT_PRICE = re.compile(r"\$\d+(?:\.\d{1,2})?/[a-z]+", re.IGNORECASE)


def _old_price(item: dict, price: Decimal) -> tuple[Decimal | None, str | None]:
    """Google's old_price is either a previous price ("$20", "Usually $37") or a unit price ("$0.31/ct")."""
    displayed = _text(item.get("old_price"))
    if not displayed:
        return None, None
    if _UNIT_PRICE.fullmatch(displayed):
        return None, displayed
    match = _USD_PRICE.fullmatch(re.sub(r"^usually\s+", "", displayed, flags=re.IGNORECASE))
    previous = _positive_price(match.group(1).replace(",", "")) if match else None
    return (previous, None) if previous is not None and previous > price else (None, None)


def search_products(query: str) -> list[ShoppingProduct]:
    """Search one page of Google Shopping; cache normalized results for 15 minutes."""
    if not query.strip():
        raise ValueError("A product query is required.")
    api_key = os.getenv("SERPAPI_KEY", "").strip()
    if not api_key:
        raise ShoppingServiceError("Shopping search is not configured (SERPAPI_KEY).", 503)
    cache_key = (query.strip().casefold(), httpx.get)
    now = time.monotonic()
    with _cache_lock:
        cached = _product_cache.get(cache_key)
        if cached and cached[0] > now:
            return [ShoppingProduct.model_validate(product.model_dump()) for product in cached[1]]
        if cached:
            _product_cache.pop(cache_key, None)
    try:
        response = httpx.get(
            SERPAPI_URL,
            params={
                "engine": "google_shopping",
                "q": query.strip(),
                "api_key": api_key,
                "gl": "us",
                "hl": "en",
                "location": "United States",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.TimeoutException:
        raise ShoppingServiceError("Shopping search timed out. Please try again.", 504) from None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403, 429}:
            raise ShoppingServiceError("Shopping provider is temporarily unavailable.", 503) from None
        raise ShoppingServiceError("Shopping provider request failed.") from None
    except httpx.RequestError:
        raise ShoppingServiceError("Unable to reach the shopping provider.") from None

    try:
        payload = response.json()
    except ValueError:
        raise ShoppingServiceError("Shopping provider returned invalid JSON.") from None
    if not isinstance(payload, dict):
        raise ShoppingServiceError("Shopping provider returned an invalid response.")
    metadata = payload.get("search_metadata")
    status = metadata.get("status") if isinstance(metadata, dict) else None
    if payload.get("error") or status == "Error":
        raise ShoppingServiceError("Shopping provider could not complete the search.")
    results = payload.get("shopping_results")
    if results is None and "shopping_results" not in payload and status == "Success":
        return []
    if not isinstance(results, list):
        raise ShoppingServiceError("Shopping provider returned invalid shopping results.")
    products = [product for item in results if (product := _normalize_product(item)) is not None]
    with _cache_lock:
        expired = [key for key, value in _product_cache.items() if value[0] <= now]
        for key in expired:
            _product_cache.pop(key, None)
        if len(_product_cache) >= MAX_CACHE_ENTRIES:
            oldest = min(_product_cache, key=lambda key: _product_cache[key][0])
            _product_cache.pop(oldest, None)
        _product_cache[cache_key] = (now + CACHE_TTL_SECONDS, products)
    return [ShoppingProduct.model_validate(product.model_dump()) for product in products]


def _tokens(text: str) -> list[str]:
    # Keep model numbers and sizes. Case and punctuation do not imply variants.
    return re.findall(r"[^\W_]+", text.casefold())


def find_alternatives(
    product_name: str,
    original_price: float,
    brand: str | None = None,
    allow_similar: bool = True,
) -> list[ShoppingAlternative]:
    """Return up to three cheaper listings; title matches do not prove identity."""
    requested = _tokens(product_name)
    brand_tokens = _tokens(brand or "")
    if not requested or not math.isfinite(original_price) or original_price <= 0:
        raise ValueError("A product name and a finite, positive original price are required.")
    search_query = product_name.strip()
    if brand_tokens and not set(brand_tokens).issubset(requested):
        search_query = f"{brand.strip()} {search_query}"
    required = set(requested) | set(brand_tokens)
    alternatives = []
    for product in search_products(search_query):
        title_tokens = _tokens(product.title)
        title_terms = set(title_tokens)
        if not required.issubset(title_terms):
            continue
        if (title_terms - required) & _NON_COMPARABLE_TERMS:
            continue
        # Model numbers supplied in the query must survive matching. Titles
        # with more detail are only similar; no original product ID is supplied
        # by this endpoint, so returned product IDs cannot prove equivalence.
        exact = title_tokens == requested or title_tokens == _tokens(search_query)
        if not allow_similar and not exact:
            continue
        with localcontext() as context:
            context.prec = 340  # Covers the full finite float range, plus cents.
            original = Decimal(str(original_price))
            difference = original - Decimal(str(product.price))
            savings = difference.quantize(_CENT, rounding=ROUND_HALF_UP)
            if savings <= 0 or difference <= 0:
                continue
            percent = (difference / original * 100).quantize(_CENT, rounding=ROUND_HALF_UP)
        alternatives.append(
            ShoppingAlternative(
                **product.model_dump(),
                match_type="exact_title_match" if exact else "similar_alternative",
                match_reason=(
                    "Normalized title matches the request; product equivalence is unverified."
                    if exact else
                    "All requested name and brand terms match; additional title details may indicate a different variant."
                ),
                potential_savings=float(savings),
                potential_savings_percent=float(percent),
            )
        )
    alternatives.sort(key=lambda product: (-product.potential_savings, product.title, product.link))
    # Repeated results must not fill all three slots; preserve distinct sellers.
    unique = []
    seen = set()
    for product in alternatives:
        identity = (product.product_id or product.title.casefold(), product.source, product.price)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(product)
        if len(unique) == 3:
            break
    return unique
