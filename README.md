# Ripple

Ripple shows the three costs of every purchase: dollars now, 30-year future value, and carbon impact, then uses SerpApi to suggest cheaper or greener alternatives.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API health check is available at `http://localhost:8000/health`.

## Environment variables

Copy `.env.example` to `.env` and provide:

- `NESSIE_API_KEY`
- `SERPAPI_KEY`
- `LLM_API_KEY`
