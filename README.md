# Ripple API

Backend-only FastAPI API for receipt scanning, itemized spending, and a demo Capital One Nessie account. Gemini vision reads receipt images. Receipts, items, and demo account IDs are kept in memory while the server is running.

## Requirements

- Python 3.11+
- A Gemini API key
- A Nessie API key (needed only for Nessie routes)

## Run locally

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Add `GEMINI_API_KEY` and, if you use the Nessie routes, `NESSIE_API_KEY` to your `.env` file. To try receipt uploads without a Gemini key, set `MOCK_MODE=true`; the scan route will save a sample receipt.

Start the server from the repository root:

```bash
uvicorn app.main:app --reload
```

Interactive API docs are at `http://localhost:8000/docs`; `GET /health` checks that the API is running.

## Example requests

Create or reuse the demo Nessie customer and checking account:

```bash
curl -X POST http://localhost:8000/nessie/setup
```

Seed about 15 purchases over the last 30 days (run setup first):

```bash
curl -X POST http://localhost:8000/nessie/seed
```

Scan a receipt image and save the receipt and its items:

```bash
curl -X POST http://localhost:8000/receipts/scan \
  -F "file=@receipt.jpg;type=image/jpeg"
```

Other useful routes include `GET /receipts`, `GET /receipts/{id}`, `GET /items?category=produce&start=2026-10-01&end=2026-10-24`, `GET /spending/summary?period=month`, and `GET /nessie/transactions`.

## Configuration notes

- `GEMINI_MODEL` defaults to `gemini-3.8-flash` and can be changed to a model available to your Gemini API key.
- Supported receipt uploads are JPEG, PNG, HEIC, and HEIF up to 15 MB.
- Receipt data and Nessie demo IDs are stored in memory and are cleared when the server restarts.
- The API enables CORS for all origins for hackathon demos. It has no authentication and is intended for a controlled demo environment.
