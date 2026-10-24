# Ripple API

FastAPI backend for receipt scanning, itemized spending, and a demo Capital One
Nessie account. Gemini reads receipt images; Supabase stores users, receipts,
items, and demo account IDs. All application database requests use the Supabase
Python SDK over HTTPS, normally port 443. No direct PostgreSQL connection is used.

## Install and configure

Requires Python 3.11+ and a Supabase project. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows use `python -m venv .venv` and `.venv\Scripts\activate`.
The root `requirements.txt` contains the backend dependencies and pytest. The
database package is `supabase`; psycopg is no longer required.

Copy `.env.example` to `.env` if you do not already have one. Existing `.env`
files should be edited rather than overwritten. The backend loads the root
`.env` regardless of the working directory; process environment variables take
precedence.

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=sb_secret_YOUR_BACKEND_KEY
```

Use the project's HTTPS URL from the Supabase dashboard and its backend secret
key from API key settings. The URL is not a PostgreSQL connection string and
should not include `/rest/v1`. A legacy `service_role` JWT is also accepted in
`SUPABASE_SECRET_KEY`; publishable and anon keys are rejected by the backend.
See [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys).

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Required project HTTPS base URL. |
| `SUPABASE_SECRET_KEY` | Required backend-only secret with service-role access. |
| `GEMINI_API_KEY` | Required for real receipt parsing. |
| `GEMINI_MODEL` | Optional; defaults to `gemini-2.5-flash`. |
| `MOCK_MODE` | `true` uses sample receipt data instead of calling Gemini. Supabase is still required. |
| `NESSIE_API_KEY` | Required only for Nessie routes. |

`DATABASE_URL` and Tiger Data credentials are no longer read by this integration.
Keep `.env` out of Git. The Supabase secret must stay on the backend; never put it
in an Expo/Vite public environment variable, browser bundle, or mobile app.

## Install the Supabase schema

1. Open your Supabase project and select **SQL Editor → New query**.
2. Paste the complete contents of `schema.sql`, review it, and click **Run**.
3. In the Data API settings, ensure the Data API is enabled and the `public`
   schema is exposed. Keep `ripple_private` out of the exposed schemas list.
4. From your project terminal, verify HTTPS access:

   ```bash
   python -m scripts.init_db
   ```

The command is now read-only. It calls `ripple_check` and prints:

```text
Supabase HTTPS connection and Ripple schema verified. No schema changes were executed.
```

The SDK cannot install arbitrary SQL through the Data API. The SQL Editor step
is required; the verification command does not create tables or functions.
A missing-function/schema error means you should run the current `schema.sql`
and allow its PostgREST schema-cache refresh to finish.

The script runs in a transaction and is idempotent: it creates missing tables
and indexes and replaces Ripple's functions without deleting rows. It also
reapplies RLS and the grants described below. It does not upgrade incompatible
existing tables or transfer data from Tiger Data. Those would require separate,
reviewed migrations. No schema script is executed automatically by FastAPI.

## Run and use the API

```bash
uvicorn app.main:app --reload
```

Interactive docs: `http://localhost:8000/docs`. Application health:
`http://localhost:8000/health`; this route does not check Supabase connectivity.
Existing route paths, query parameters, status behavior, and successful receipt
response fields are retained.

Upload a JPEG, PNG, HEIC, or HEIF receipt up to 15 MB:

```bash
curl -X POST http://localhost:8000/receipts/scan \
  -F "file=@receipt.jpg;type=image/jpeg"
```

For a scan without Gemini, set `MOCK_MODE=true` before starting FastAPI. Mock mode
returns sample receipt data for a nonempty upload with an allowed MIME type.

Other routes:

- `GET /receipts` and `GET /receipts/{id}`: saved receipt history and details.
- `GET /items?category=produce&start=2026-10-01&end=2026-10-24`: item filtering with inclusive dates.
- `GET /spending/summary?period=month`: rolling `week` (7 days), `month` (30 days), or `all`, grouped by category and UTC day.

Create/reuse the Nessie demo account and seed 15 sample purchases:

```bash
curl -X POST http://localhost:8000/nessie/setup
curl -X POST http://localhost:8000/nessie/seed
curl http://localhost:8000/nessie/transactions
```

To verify persistence, upload a receipt, record its `id`, restart FastAPI, and
retrieve `GET /receipts/{id}` using the same Supabase project. The receipt and
items should remain available. Supabase API errors and HTTPS timeouts return
sanitized database errors through the existing 503 handlers. Invalid receipt
item quantities or negative prices return 422.

## Storage and atomic receipt creation

| Table | Contents |
| --- | --- |
| `public.users` | UUID, unique username, creation time, optional Nessie demo IDs. Separate from Supabase `auth.users`. |
| `public.receipts` | Owning user, merchant/date/totals, raw parsed JSON and creation time. |
| `public.receipt_items` | Owning receipt, raw/expanded name, category, quantity/prices, timestamps and line order. |

Foreign keys connect users → receipts → items. Deleting a receipt cascades to
its items; users with receipts cannot be deleted. Constraints validate required
fields, positive quantities, allowed categories, and finite nonnegative prices.
Indexes support user history, receipt lines, categories, and purchase dates.
Money and quantities use PostgreSQL `NUMERIC` without fixed-scale rounding.
Refunds/negative item prices are not supported by this MVP.

`app/storage.py` keeps its public functions, including optional `user_id`
arguments. Existing endpoints have no user identity and use the shared
`ripple-demo` user. User helpers do not provide authentication. The SQL fields
`merchant`/`expanded_name` map to the existing `store_name`/`full_name` response
fields. Raw JSON, warnings, UUIDs, dates, timestamps, and item order are retained.

Every save calls **one** `ripple_save_receipt` RPC. This PostgreSQL function
creates the demo user if needed, inserts the receipt and every item, and returns
the saved document in one transaction. An invalid second item rolls back the
entire save. There are no separate client-side insert calls or swallowed SQL
exceptions. See [Supabase database functions](https://supabase.com/docs/guides/database/functions).

Read RPCs return numeric values as decimal **strings**, which Python restores to
`Decimal` before FastAPI serializes responses. This prevents precision loss from
the SDK's normal JSON float parsing, including for spending aggregates. Small
JSON helpers live in the unexposed `ripple_private` schema. Collection RPCs return
JSON arrays, avoiding silent truncation by the Data API's table row limit; very
large histories may need pagination in a future API version.

HTTPS calls have a 15-second timeout, use closed HTTP transport contexts, and do
not automatically retry writes. If a response is lost after a commit, the client
cannot know whether the save succeeded; check history before retrying. Receipt
uploads currently have no idempotency key.

## Access controls

All three tables have RLS enabled. The schema grants no table access to `PUBLIC`,
`anon`, or `authenticated`, and creates no permissive client policies. It also
revokes execution on every Ripple RPC from those roles. Only `service_role`
receives table SELECT/INSERT/UPDATE and function EXECUTE privileges. All RPCs use
`SECURITY INVOKER`, an empty search path, and schema-qualified references.
Supabase secret keys run with service-role privileges and bypass RLS, which is
why the key stays exclusively on the backend.

The existing FastAPI demo endpoints still have no authentication and permit
CORS from all origins. These Supabase restrictions protect direct Data API
access; they do not authenticate callers of FastAPI. Add API authentication and
trusted user ownership before making this shared demo API publicly available.

## Tests

```bash
pip install -r requirements.txt
python -m pytest -q
```

Default tests exercise the **real Supabase SDK** against mocked HTTPS responses.
They replace local credentials, make no cloud calls, and mock Gemini/Nessie in
route tests. Coverage includes receipt/line response contracts, exact decimals,
user helpers and scoping parameters, filters, summaries, single-RPC saves,
validation, missing/incorrect credentials, failed requests, timeout behavior,
transport cleanup, error redaction, and health/Nessie endpoint compatibility.

For actual SQL transaction, constraint, precision, and RLS/grant regression
checks, review and run `tests/sql/test_storage.sql` in the SQL Editor after
installing the schema. All its test writes are enclosed in a transaction that
ends with `ROLLBACK`. If it fails, roll back the open transaction before
continuing. It does not delete existing data or alter tables.

Optional read-only live SDK tests require explicit opt-in and separate test
credentials; application credentials are never used automatically:

```bash
export TEST_SUPABASE_URL='https://YOUR_TEST_PROJECT.supabase.co'
export TEST_SUPABASE_SECRET_KEY='YOUR_TEST_BACKEND_SECRET'
# Optional: also set TEST_SUPABASE_PUBLISHABLE_KEY for anonymous-denial checks.
python -m pytest tests/integration --run-db-integration -q
```

On PowerShell use `$env:VARIABLE='value'` instead of `export`. Live tests verify
schema access and reads; they never insert/delete cloud records. The SQL Editor
checks verify transaction rollback and role grants inside PostgreSQL itself.
