from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.routers.nessie import router as nessie_router
from backend.routers.predictions import router as predictions_router
from backend.routers.receipts import router as receipts_router
from backend.routers.shopping_list import router as shopping_list_router
from backend.routers.shopping import router as shopping_router
from backend.routers.spending import router as spending_router


# Resolve the shared root .env independently of the process working directory.
# Existing process environment variables always take precedence.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Ripple API")
app.include_router(shopping_router)
app.include_router(shopping_list_router)
app.include_router(receipts_router)
app.include_router(spending_router)
app.include_router(nessie_router)
app.include_router(predictions_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
