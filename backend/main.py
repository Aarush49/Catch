from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.nessie import router as nessie_router
from backend.routers.auth import router as auth_router
from backend.routers.predictions import router as predictions_router
from backend.routers.receipts import router as receipts_router
from backend.routers.shopping_list import router as shopping_list_router
from backend.routers.shopping import router as shopping_router
from backend.routers.spending import router as spending_router
from backend.services.sqlite_store import init_db


# Resolve the shared root .env independently of the process working directory.
# Existing process environment variables always take precedence.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="Ripple API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(shopping_router)
app.include_router(shopping_list_router)
app.include_router(receipts_router)
app.include_router(spending_router)
app.include_router(nessie_router)
app.include_router(predictions_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
