# Ripple

Ripple shows the three costs of every purchase: dollars now, 30-year future value, and carbon impact, then uses SerpApi to suggest cheaper or greener alternatives.

## Frontend

```bash
cd frontend
npm install
npx expo start
```

Open the QR code in Expo Go, or press `a` for Android / `i` for iOS when a simulator is available.

## Backend

Requires Python 3.10+ (tested with Python 3.13). Run these commands from the
repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
# Set SERPAPI_KEY in .env before using shopping search.
uvicorn backend.main:app --reload
```

On Windows, create the environment with `python -m venv .venv`, activate with
`.venv\Scripts\activate`, and use `copy .env.example .env`.

The existing API health check is available at `http://localhost:8000/health`.
Interactive API documentation is at `http://localhost:8000/docs`.

## Environment variables

The backend loads the repository-root `.env` automatically; existing process
environment variables take precedence. Keep `.env` private (it is gitignored)
and never place secrets in frontend environment variables.

| Variable | Purpose |
| --- | --- |
| `SERPAPI_KEY` | Required for shopping search; get a key from [SerpAPI](https://serpapi.com/manage-api-key). Backend only. |
| `NESSIE_API_KEY` | Reserved for the banking integration; not required for shopping. |
| `LLM_API_KEY` | Reserved for the AI integration; not required for shopping. |

## Shopping alternatives

`GET /api/shopping/alternatives` searches one page of SerpAPI's
[`google_shopping` engine](https://serpapi.com/google-shopping-api) in the US and
returns up to three cheaper, potentially comparable listings, ordered by highest
potential savings. No other engines or integrations are called.

| Query parameter | Required | Description |
| --- | --- | --- |
| `query` | Yes | Product name, 1–200 characters; include model, size, or capacity when known. |
| `original_price` | Yes | Finite, positive original price in USD. |
| `brand` | No | Brand name, 1–100 characters; included in search and title matching. |

```bash
curl --get 'http://localhost:8000/api/shopping/alternatives' \
  --data-urlencode 'query=Nike Air Force 1' \
  --data-urlencode 'original_price=120' \
  --data-urlencode 'brand=Nike'
```

Illustrative response (not a live offer; optional missing fields are `null`):

```json
{
  "query": "Nike Air Force 1",
  "original_price": 120.0,
  "alternatives": [
    {
      "title": "Nike Air Force 1 Low White",
      "price": 90.0,
      "source": "Example Merchant",
      "rating": null,
      "link": "https://example.com/products/air-force-1",
      "thumbnail": null,
      "product_id": null,
      "match_type": "similar_alternative",
      "match_reason": "All requested name and brand terms match; additional title details may indicate a different variant.",
      "potential_savings": 30.0,
      "potential_savings_percent": 25.0
    }
  ],
  "currency": "USD",
  "savings_note": "Potential savings compare listing prices only. Product equivalence is not verified; check model, size, quantity, condition, and seller. Shipping and taxes may be additional, and the original price may include different costs."
}
```

Every requested name and brand token must appear in the listing title, including
model numbers. `exact_title_match` means only that the title matches after case
and punctuation normalization. `similar_alternative` means all required terms
appear with additional details. Neither classification verifies equivalence;
product IDs are retained but cannot identify the original product because the
request contains no original ID. This intentionally conservative heuristic can
miss valid alternatives and can still admit different variants or pack sizes.
It does not infer sustainability, authenticity, or availability.

Invalid listings, common accessories not requested by name, explicitly secondhand
listings, installment offers, ambiguous prices, and explicitly non-USD prices are
excluded. Numeric prices without a currency label are treated as USD because the
search uses US localization. Listing prices are normalized to cents. Savings are
calculated with Python `Decimal` and rounded to cents using half-up rounding;
percentages use the unrounded difference and are rounded to two decimal places.
Differences that round to zero cents are omitted. Shipping and tax are not added
or assumed to be included. Compare the original price on the same basis.

No results or no qualifying cheaper listings returns HTTP 200 with
`"alternatives": []`. Errors use FastAPI's `{"detail": "..."}` format:

| Status | Meaning |
| --- | --- |
| `422` | Missing, blank, oversized, or invalid query parameters; nonpositive or nonfinite price. |
| `502` | Provider HTTP/network failure, API error payload, or malformed response. |
| `503` | Missing `SERPAPI_KEY`, or provider HTTP 401/403/429 (credentials/quota). |
| `504` | Provider request timed out (15-second HTTP timeout). |

Provider error text, request URLs, and API keys are not included in public errors.
The endpoint makes one search request without automatic retries. There is no
application cache because the repository has no caching mechanism. Repeated
requests may consume SerpAPI credits; use the mocked tests during development.

## Backend tests

From the repository root, with the virtual environment activated:

```bash
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
```

Tests mock all SerpAPI HTTP calls and replace local credentials with a fake key.
They cover normalization, missing/invalid prices and optional fields, matching and
accessory exclusions, cheaper-price filtering, decimal savings, sorting and the
three-result limit, deduplication, credentials, HTTP/API/JSON/network failures,
timeouts, endpoint validation, response schemas, and the existing health route.
Use the curl example above for an optional live smoke test with a configured key;
it can consume one search credit.

The integration lives in `backend/services/serpapi_service.py`, response models in
`backend/models.py`, and the route in `backend/routers/shopping.py`. Future work
can add identifier/variant verification and separate providers for Google Product,
Amazon Product, or eBay Search without changing this endpoint's core purpose.
