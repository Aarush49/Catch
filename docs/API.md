# Authenticated API reference

See [the README](../README.md) for Supabase configuration and schema installation.

## Account and bank data

Accounts are Supabase Auth users; the app signs up and signs in with the
Supabase client. Send the session's access token as
`Authorization: Bearer <token>` to user data endpoints. The backend verifies it
against the project's signing keys and uses its `sub` claim as the user ID.

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

Upload a JPEG, PNG, WebP, or HEIC image (up to 8 MB) as multipart field `file`:

```bash
curl -X POST http://localhost:8000/receipts/scan \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -F "file=@receipt.jpg;type=image/jpeg"
```

Gemini returns `merchant`, `purchased_at`, `subtotal`, `tax`, `total`, and
`items` (`name`, `quantity`, line-total `price`, `category`), plus
`needs_review`/`review_reason` when the items do not add up to the subtotal.
Nothing is saved. After the user reviews it, the app saves the receipt with the
`save_receipt` database function, storing each item's unit price and an
illustrative category-by-dollar `carbon_kg_co2e` estimate. The app reads
receipts directly from Supabase.

## Spending history

`GET /api/spending/history?days=90` returns daily, Monday-start weekly, and
monthly totals for persisted bank expenses in the selected recent date range,
and an `income_total` for saved salary deposits. Receipts are not included.

## Nessie sandbox

The quickest path is the one-tap demo bank (the app's **Connect demo bank**
button on Profile):

```bash
curl -X POST http://localhost:8000/api/nessie/demo-bank \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

It creates a sandbox customer and checking account, adds 15 purchases from the
last month plus one paycheck deposit, links the account and imports it, then
returns `{account_id, count, transactions, created}`. Calling it again does not
create a second bank: it re-imports the linked account (`created: false`).
Nessie stores whole-dollar amounts for purchases, deposits and transfers.

The demo bank also gets six monthly bills and a `CATch savings` account. Each
import stores, in the same `transactions` table:

- purchases with their merchant's spending category (`groceries`, `restaurant`,
  `household`, `health`, `transportation`, `other`);
- upcoming bills as `transaction_type = 'bill'`, dated on their next payment
  date (bills deleted in Nessie are removed);
- deposits into `CATch savings` as `transaction_type = 'savings'`.

Spending totals count only purchases and withdrawals, and income only paychecks,
so bills, savings and transfers are never counted as spending or income. Calling
`demo-bank` on a demo account made before bills existed adds its bills.

Move money into savings (the app does this after you apply swaps on Compare):

```bash
curl -X POST http://localhost:8000/api/nessie/savings \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" -H "Content-Type: application/json" \
  -d '{"amount": 7.49, "description": "Tide Pods swap"}'
```

The amount is rounded to the nearest dollar (under $0.50 moves nothing). It is
deposited into `CATch savings` (created on first use) and recorded as a transfer
out of checking. The response is `{moved, savings_total}`.

To link an existing sandbox account instead, use `GET /api/nessie/customers`, then
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
unchecked item and `total_potential_savings`, based on each item's best listed
saving. Items without a price (for example, ones added in the app) are listed
with `original_price: null` and an `error` asking for a price.
With `allow_lower_quality: false`, only exact normalized-title matches are
returned; `true` also allows similar-title matches. Neither mode proves product
equivalence or quality.

## Future-value projection

`POST /api/predictions` needs no login. It accepts `amount`, optional
`alternative_amount`, `years` (1-100, default 30), and `annual_return` (0-1,
default 0.07). Without `times_per_month` it compounds the one-time difference
between the original and alternative amounts once a year.

Add `times_per_month` for a recurring purchase. `recurring.monthly_savings` is
`(amount - alternative_amount) × times_per_month`, put aside at the end of every
month and grown at the monthly rate equivalent to `annual_return`.
`recurring.total_saved` is the money set aside before growth, and
`recurring.future_savings` is its value after `years`. The Predict screen sends
`times_per_month` and shows `recurring.future_savings`.

`explanation` is one sentence. `explanation_source` is `gemini` when Gemini
wrote it, or `fallback` when Gemini is unavailable, times out (10 s), is over
quota, or replies without the projected amount. After a quota error the API
uses the fallback for Gemini's suggested retry delay. Gemini sentences are
cached per amount, so repeated inputs do not spend quota. Nothing is saved
server-side; the Predict screen stores a chosen goal in the signed-in user's
Supabase `user_metadata.predict_goal` (on the device for demo sessions).

```json
{"amount":50,"alternative_amount":35,"years":30,"annual_return":0.07,"times_per_month":2}
```
