# $\color{yellow}{Cat}$ch

Expo app and FastAPI backend for receipt scanning, spending history, shopping
comparisons, Nessie banking, and financial predictions.

## How the pieces fit

- **Supabase** is the single database and login system. `supabase/schema.sql`
  defines every table. Each row belongs to a Supabase Auth user, and row level
  security (RLS) limits users to their own rows.
- **The app** (`frontend/`) signs in with Supabase Auth and reads and writes
  receipts directly through Supabase with the publishable/anon key.
- **The backend** (`app/` + `backend/`) only does work that needs secret keys:
  Gemini receipt reading, SerpAPI price comparison, and Nessie bank imports. It
  accepts the same Supabase session token the app already has.

Receipt flow: the app uploads a photo to `POST /receipts/scan` → the backend
asks Gemini to read it and returns the result **without saving** → the user
reviews it → the app calls the `save_receipt` database function, which saves
the receipt and all of its items in one transaction (or none of them).

## 1. Database

1. In your Supabase project, open **SQL Editor → New query**, paste all of
   `supabase/schema.sql`, and click **Run**. It is safe to re-run.
   - If the project still has the old backend tables (`users`, `sessions`, …),
     the script removes them first, but only if they are empty; otherwise it
     stops without changing anything.
2. Under **Authentication → Sign In / Providers → Email**, decide whether new
   users must confirm their email. With confirmation on, sign-up asks the user
   to confirm before signing in.

## 2. Backend

Requires Python 3.11+. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # only if you do not have a .env yet; then fill it in
python -m scripts.init_db          # read-only: confirms the schema is installed
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Project URL, e.g. `https://abcd.supabase.co`. |
| `SUPABASE_SECRET_KEY` | Secret (service-role) key, backend only. |
| `SUPABASE_JWT_SECRET` | Only for projects on the legacy shared JWT secret; otherwise tokens are checked against the project's public signing keys automatically. |
| `API_NINJAS_KEY` | Receipt image OCR. Receipt fields are parsed locally by the backend. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Prediction explanations. |
| `SERPAPI_KEY` | Shopping comparisons. |
| `NESSIE_API_KEY` | Bank sandbox routes. |

API docs: `http://localhost:8000/docs`.

| Route | Auth | Purpose |
| --- | --- | --- |
| `GET /health` | none | Liveness check. |
| `POST /receipts/scan` | Supabase session | Read a receipt photo with Gemini; nothing is saved. |
| `GET/POST /api/shopping-list/items`, `DELETE /api/shopping-list/items/{id}` | Supabase session | Shopping list rows (same `shopping_items` table the app can read). |
| `POST /api/shopping-list/done` | Supabase session | Compare unchecked, priced list items with SerpAPI. |
| `GET /api/nessie/customers`, `GET /api/nessie/customers/{id}/accounts` | Supabase session | Browse the Nessie sandbox. |
| `POST /api/nessie/link`, `GET /api/nessie/transactions` | Supabase session | Link an account and import its transactions. |
| `GET /api/spending/history` | Supabase session | Totals from imported bank transactions. |
| `GET /api/shopping/alternatives` | none | One-off SerpAPI search. |
| `POST /api/predictions` | none | Long-term savings projections. |

The backend's secret key bypasses RLS, so every backend query filters by the
user ID from the verified session token. Users can read, but not write, their
`linked_accounts` and `transactions`; only the backend writes bank data.

## 3. App

```bash
cd frontend
cp .env.example .env   # then fill in the values
npm install
npx expo start
```

Use the **publishable/anon** key in `frontend/.env`, never the secret key. On
a physical phone, `EXPO_PUBLIC_API_URL` must be your computer's LAN IP and both
devices must be on the same network. `EXPO_PUBLIC_DEMO_MODE=true` runs the app
on sample data with no backend or database.

## Tests

```bash
python -m pytest -q
```

These use the real Supabase SDK against mocked HTTPS responses and make no
network calls. To check the live project end to end:

```bash
python -m scripts.verify_pipeline
```

That script creates two temporary users, saves/edits receipts as one, confirms
the other cannot see or change them, exercises the backend with real session
tokens, and then deletes both users and everything they created.
