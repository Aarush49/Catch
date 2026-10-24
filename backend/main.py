from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.routers.shopping import router as shopping_router


# Resolve the shared root .env independently of the process working directory.
# Existing process environment variables always take precedence.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Ripple API")
app.include_router(shopping_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
