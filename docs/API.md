# Authenticated API reference

See [the README](../README.md) for Supabase configuration and schema installation.

## Account and bank data

`POST /api/auth/signup` and `POST /api/auth/login` accept `email` and
`password` (minimum 8 characters), and return a bearer token. Send it as
`Authorization: Bearer <token>` for user data endpoints. `GET /api/auth/me`
returns the signed-in user; `POST /api/auth/logout` invalidates that session.

Nessie is a Capital One **sandbox**, not a connection to a real bank. With a
sandbox API key configured, list sandbox customers and accounts, then call
`POST /api/nessie/link` with the chosen IDs. `GET /api/nessie/transactions`
fetches and stores that account's purchases, deposits, withdrawals, and
transfers. Deposits whose description says salary/payroll/paycheck/wages are
marked as salary income. The endpoint returns the stored history. Requests
require the signed-in user's bearer token.

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
The endpoint makes one search request without automatic retries. Normalized
results are cached in process memory for 15 minutes (up to 256 queries), reducing
repeat SerpAPI use during a demo. The cache is cleared when the backend restarts.

## Receipts and carbon

Upload a JPEG, PNG, or WebP image (up to 15 MB) as multipart field `file`:

```bash
curl -X POST http://localhost:8000/api/receipts/scan \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -F "file=@receipt.jpg;type=image/jpeg"
```

Gemini returns the store, date, receipt total, and item names, prices, and
categories. The API adds `carbon_kg_co2e` to each item using a hardcoded
category-by-dollar estimate. These factors are illustrative, not product-level
life-cycle measurements. Read scans with `GET /api/receipts` and
`GET /api/receipts/{receipt_id}`.

## Spending history

`GET /api/spending/history?days=90` returns daily, Monday-start weekly, and
monthly totals for persisted bank expenses in the selected recent date range,
and an `income_total` for saved salary deposits. This preserves main's current
bank-history calculation; receipt lines are queried through receipt endpoints.

## Nessie sandbox

Use `GET /api/nessie/customers`, then
`GET /api/nessie/customers/{customer_id}/accounts` to find a sandbox account.
Link it with:

```bash
curl -X POST http://localhost:8000/api/nessie/link \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"CUSTOMER_ID","account_id":"ACCOUNT_ID"}'
```

Then call `GET /api/nessie/transactions` with the same bearer token to fetch the account history. Nessie
credentials stay in backend `.env`; requests use HTTPS. Linked account and
imported transactions persist per user in Supabase over HTTPS.

## Shopping list

Add an item with `POST /api/shopping-list/items`, for example:

```json
{"name":"Acme Widget","price":30,"brand":"Acme","category":"electronics","allow_lower_quality":false}
```

Read or remove items with `GET /api/shopping-list/items` and
`DELETE /api/shopping-list/items/{item_id}`. When the user finishes the list,
call `POST /api/shopping-list/done`. The response contains alternatives for each
item and `total_potential_savings`, based on each item's best listed saving.
With `allow_lower_quality: false`, only exact normalized-title matches are
returned; `true` also allows similar-title matches. Neither mode proves product
equivalence or quality.

## Future-value projection

`POST /api/predictions` accepts `amount`, optional `alternative_amount`, `years`
(default 30), and `annual_return` (default 0.07). It compounds the difference
between the original and alternative amounts. Add `times_per_month` for
annualized recurring spend and a recurring projection. Gemini writes the short
explanation when available; the calculation still returns a fallback sentence
if Gemini is unavailable.

```json
{"amount":50,"alternative_amount":35,"years":30,"annual_return":0.07,"times_per_month":2}
```
