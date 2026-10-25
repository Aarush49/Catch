# CATch

FastAPI backend and Expo UI f
or receipt scanning, spending history, Nessie
banking, shopping comparisons, and financial predictions. Supabase stores users,
sessions, bank links, transactions, receipts, receipt items, and shopping items.
All application database requests use the Supabase Python SDK over HTTPS, normally port 443. No direct PostgreSQL connection is used.

## Frontend

```bash
cd frontend
npm install
npx expo start
```

Open the QR code in Expo Go or start an available simulator. The current Expo
screens use Supabase Auth and database-backed receipts. Copy `frontend/.env.example`
to `frontend/.env` and fill in the Supabase URL and anon key. On a physical phone,
`EXPO_PUBLIC_API_URL` must use your computer's LAN IP (for example
`http://192.168.x.x:8000`), not localhost; the phone and computer must be on the
same network. Set `EXPO_PUBLIC_DEMO_MODE=true` only for an offline mock demo.

Start the API so phones on the LAN can reach it:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Create a Supabase project, run `supabase/schema.sql` in its SQL Editor, and copy
the project values into the frontend and backend environment files. Obtain a
Gemini API key from Google AI Studio and keep it only in the backend `.env`.

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
| `GEMINI_MODEL` | Optional shared model override; choose a model enabled for your key. |
| `MOCK_MODE` | Sample parsing for the legacy `/receipts/scan` route only; `/api/receipts/scan` uses Gemini. Supabase is still required. |
| `NESSIE_API_KEY` | Required only for Nessie routes. |
| `SERPAPI_KEY` | Required for shopping comparisons and alternatives. |

`DATABASE_URL` and Tiger Data credentials are no longer read by this integration.
Keep `.env` out of Git. The Supabase secret must stay on the backend; never put it
in an Expo/Vite public environment variable, browser bundle, or mobile app.

## Install the Supabase schema

1. Open your Supabase project and select **SQL Editor → New query**.
2. Paste the complete contents of `schema.sql`, review it, and click **Run**.
3. In the Data API settings, ensure the Data API is enabled and the `public`
   schema is exposed. Keep `CATch_private` out of the exposed schemas list.
4. From your project terminal, verify HTTPS access:

   ```bash
   python -m scripts.init_db
   ```

The command is now read-only. It calls `CATch_check` and prints:

```text
Supabase HTTPS connection and CATch schema verified. No schema changes were executed.
```

The SDK cannot install arbitrary SQL through the Data API. The SQL Editor step
is required; the verification command does not create tables or functions.
A missing-function/schema error means you should run the current `schema.sql`
and allow its PostgREST schema-cache refresh to finish.

The script runs in a transaction and is idempotent: it creates missing tables,
indexes, and functions without deleting rows. It upgrades the known receipt-only
schema to version 2 by adding account credential columns, carbon estimates, four
new tables, and their RPCs. It widens the receipt category constraint to accept
`utilities`, and reapplies RLS/grants on all seven tables. Existing receipt/user
IDs and rows are retained. It does not migrate records from a local SQLite file
or Tiger Data, or repair arbitrary incompatible schemas. Those would require separate,
reviewed migrations. No schema script is executed automatically by FastAPI.

## Run and use the API

```bash
uvicorn backend.main:app --reload
```

Interactive docs: `http://localhost:8000/docs`. Application health:
`http://localhost:8000/health`; this route does not check Supabase connectivity.
Both `backend.main:app` and `app.main:app` expose the same combined application.
Main's authenticated `/api/*` routes and the earlier legacy routes retain their
successful response formats. Database failures return sanitized HTTP 503 errors.
No SQLite file is created during startup.

For the authenticated API, sign up or log in at `POST /api/auth/signup` or
`POST /api/auth/login` with JSON `{"email":"you@example.com","password":"your-password"}`.
Use the returned `access_token` in `Authorization: Bearer YOUR_ACCESS_TOKEN`.
Sessions last 30 days; `POST /api/auth/logout` revokes the current session.

| Route | Purpose |
| --- | --- |
| `GET /api/auth/me` | Signed-in user profile. |
| `POST /api/receipts/scan` | Authenticated receipt scan; returns store/date/items/carbon estimates. |
| `GET /api/receipts`, `GET /api/receipts/{id}` | The signed-in user's receipt history/details. |
| `GET/POST /api/shopping-list/items`, `DELETE /api/shopping-list/items/{id}` | Per-user shopping list. |
| `POST /api/shopping-list/done` | Compare the current shopping list with SerpAPI. |
| `GET /api/nessie/customers`, `GET /api/nessie/customers/{id}/accounts` | Nessie sandbox lookup. |
| `POST /api/nessie/link`, `GET /api/nessie/transactions` | Link a bank account and upsert imported transactions for this user. |
| `GET /api/spending/history` | Main's bank expense/income history; does not double-count receipt lines. |
| `GET /api/shopping/alternatives` | Existing product alternatives search. |
| `POST /api/predictions` | Existing long-term projections. |

See [the API reference](docs/API.md) for the imported shopping, carbon, bank, and prediction details.

Example authenticated scan:

```bash
curl -X POST http://localhost:8000/api/receipts/scan \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -F 'file=@receipt.jpg;type=image/jpeg'
```

For a controlled demo, optionally run `python -m scripts.seed_supabase_demo`.
This writes an account and four repeatable sample transactions to Supabase.
The default demo login is `demo@CATch.local` / `CATchDemo123!`; override it with
`CATch_DEMO_EMAIL` and `CATch_DEMO_PASSWORD` for a private demo. Re-running
updates the same external transaction IDs. The legacy command
`python scripts/seed_sqlite_demo.py` delegates to this Supabase seed and no longer
opens SQLite.

The earlier receipt-only endpoints below remain available for compatibility.
They use a shared demo user rather than the signed-in user's identity.

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
| `public.users` | UUID, legacy username, optional unique email and salted PBKDF2 password hash, creation time and legacy demo IDs. Separate from `auth.users`. |
| `public.sessions` | SHA-256 session token hashes, user reference and expiry; plaintext tokens are never stored. |
| `public.linked_accounts` | One Nessie customer/account link per user. |
| `public.transactions` | Per-user bank/demo transactions; exact amounts and unique `(user_id, source, external_id)` import keys. |
| `public.shopping_items` | Per-user products, prices, brands, categories and quality preference. |
| `public.receipts` | Owning user, merchant/date/totals, raw parsed JSON and creation time. |
| `public.receipt_items` | Owning receipt, raw/expanded name, category, quantity/prices, timestamps and line order. |

Foreign keys connect users → receipts → items. Deleting a receipt cascades to
its items; users with receipts cannot be deleted. Constraints validate required
fields, positive quantities, allowed categories, and finite nonnegative prices.
Indexes support user history, receipt lines, categories, and purchase dates.
Money and quantities use PostgreSQL `NUMERIC` without fixed-scale rounding.
Refunds/negative item prices are not supported by this MVP.

`app/storage.py` keeps its public functions, including optional `user_id`
arguments. Legacy receipt-only endpoints have no user identity and use the shared
`CATch-demo` user. User helpers do not provide authentication. The SQL fields
`merchant`/`expanded_name` map to the existing `store_name`/`full_name` response
fields. Raw JSON, warnings, UUIDs, dates, timestamps, and item order are retained.
The new `backend/services/supabase_store.py` adapts the SQLite-era function
contracts to these same tables/RPCs. Main's `name`/`price` item fields map to
`expanded_name`/`total_price`; carbon estimates are stored in `carbon_kg_co2e`.
Line ownership is derived from the parent receipt rather than duplicating its
user ID. Old lines without an estimate initialize to zero; new scans persist the
estimated value. The previous `sqlite_store` module is only an import shim.

Every save calls **one** `CATch_save_receipt` RPC. This PostgreSQL function
creates the demo user if needed, inserts the receipt and every item, and returns
the saved document in one transaction. An invalid second item rolls back the
entire save. There are no separate client-side insert calls or swallowed SQL
exceptions. See [Supabase database functions](https://supabase.com/docs/guides/database/functions).

Read RPCs return numeric values as decimal **strings**, which Python restores to
`Decimal` before FastAPI serializes responses. This prevents precision loss from
the SDK's normal JSON float parsing, including for spending aggregates. Small
JSON helpers live in the unexposed `CATch_private` schema. Collection RPCs return
JSON arrays, avoiding silent truncation by the Data API's table row limit; very
large histories may need pagination in a future API version.

HTTPS calls have a 15-second timeout, use closed HTTP transport contexts, and do
not automatically retry writes. If a response is lost after a commit, the client
cannot know whether the save succeeded; check history before retrying. Receipt
uploads currently have no idempotency key.

## Access controls

All seven tables have RLS enabled. The schema grants no table access to `PUBLIC`,
`anon`, or `authenticated`, and creates no permissive client policies. It also
revokes execution on every CATch RPC from those roles. Only `service_role`
receives table SELECT/INSERT/UPDATE and function EXECUTE privileges, plus DELETE
on sessions and shopping items for logout and list removal. All RPCs use
`SECURITY INVOKER`, an empty search path, and schema-qualified references.
Supabase secret keys run with service-role privileges and bypass RLS, which is
why the key stays exclusively on the backend.

Main's private `/api/*` routes use the existing backend login/session flow and
scope database operations to the verified session's user. Authentication remains
custom PBKDF2 plus opaque session tokens for compatibility; it does not use
Supabase Auth. Keep the shared legacy demo endpoints and public demo seed out of
a production deployment. CORS remains enabled for the demo; configure trusted
origins and production authentication controls before a public launch.

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
checks, review and run `tests/sql/test_storage.sql` and
`tests/sql/test_authenticated_storage.sql` in the SQL Editor after
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

The default pytest command includes both `tests/` and `backend/tests/`, including
the imported SerpAPI tests. Merge integration tests cover signup/login/logout,
hashed credentials/tokens, per-user receipt/transaction/shopping calls, carbon
persistence, banking imports, and both API entry points. SQL tests cover fresh
installation and the receipt-only schema upgrade, atomic batch/receipt rollback,
transaction deduplication, session expiry/revocation, ownership, and role grants.
