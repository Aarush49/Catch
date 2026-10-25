import os
from datetime import date, timedelta
from typing import Any, Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import storage
from app.database import DatabaseError
from app.models import ParsedReceipt
from app.nessie import NessieClient, NessieError
from backend.services.receipt_scanner import scan_image
from backend.services.supabase_jwt import require_supabase_user

load_dotenv()

app = FastAPI(title="Ripple API", description="Receipt and spending API")
allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@app.exception_handler(DatabaseError)
async def database_error_handler(_request, exc: DatabaseError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/receipts/scan")
def scan_receipt(file: UploadFile = File(...), _user=Depends(require_supabase_user)) -> dict[str, Any]:
    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Upload a JPEG, PNG, WebP, or HEIC image.")
    image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
    try:
        return scan_image(image_bytes, mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from None


@app.get("/receipts")
def receipts() -> list[dict[str, Any]]:
    try:
        return storage.list_receipts()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read receipts: {exc}") from exc


@app.get("/receipts/{receipt_id}")
def receipt(receipt_id: UUID) -> dict[str, Any]:
    try:
        result = storage.get_receipt(receipt_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read receipt: {exc}") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return result


@app.get("/items")
def items(
    category: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end.")
    try:
        return storage.list_items(category, start, end)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read items: {exc}") from exc


@app.get("/spending/summary")
def summary(period: Literal["week", "month", "all"] = "month") -> dict[str, Any]:
    try:
        return storage.spending_summary(period)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not build spending summary: {exc}") from exc


def _id(record: dict[str, Any]) -> str:
    value = record.get("_id") or record.get("id")
    if not value:
        raise NessieError("Nessie response did not include an object ID")
    return str(value)


@app.post("/nessie/setup")
def nessie_setup() -> dict[str, str]:
    try:
        saved = storage.get_demo_ids()
        if saved:
            return {"customer_id": saved[0], "account_id": saved[1], "status": "reused"}
        client = NessieClient()
        customer = next((c for c in client.get_customers()
                         if c.get("first_name") == "Ripple" and c.get("last_name") == "Demo"), None)
        if customer is None:
            customer = client.create_customer({
                "first_name": "Ripple", "last_name": "Demo",
                "address": {"street_number": "1", "street_name": "Demo Street", "city": "San Francisco",
                            "state": "CA", "zip": "94103"},
            })
        customer_id = _id(customer)
        accounts = client.get_accounts(customer_id)
        account = next((a for a in accounts if a.get("nickname") == "Ripple Demo Checking"), None)
        if account is None:
            account = client.create_account(customer_id, {
                "type": "Checking", "nickname": "Ripple Demo Checking", "rewards": 0,
                "balance": 2500, "account_number": "1000000000000000",
            })
        account_id = _id(account)
        storage.set_demo_ids(customer_id, account_id)
        return {"customer_id": customer_id, "account_id": account_id, "status": "created or reused"}
    except NessieError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Nessie setup failed: {exc}") from exc


@app.get("/nessie/transactions")
def nessie_transactions() -> dict[str, Any]:
    try:
        ids = storage.get_demo_ids()
        if not ids:
            raise HTTPException(status_code=409, detail="Run POST /nessie/setup first.")
        return {"account_id": ids[1], "purchases": NessieClient().get_purchases(ids[1])}
    except HTTPException:
        raise
    except NessieError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not load Nessie transactions: {exc}") from exc


@app.post("/nessie/seed")
def seed_nessie() -> dict[str, Any]:
    try:
        ids = storage.get_demo_ids()
        if not ids:
            raise HTTPException(status_code=409, detail="Run POST /nessie/setup first.")
        client = NessieClient()
        merchants = client.get_merchants()
        if not merchants:
            raise HTTPException(status_code=502, detail="Nessie has no merchants available to seed purchases.")
        purchases = [
            ("weekly groceries", 63.42), ("coffee", 5.75), ("fuel", 42.10),
            ("pharmacy", 18.36), ("lunch", 14.80), ("household supplies", 27.49),
            ("produce", 22.15), ("dinner", 38.20), ("bakery", 9.60),
            ("transit pass", 25.00), ("snacks", 11.32), ("pet supplies", 31.88),
            ("hardware", 16.99), ("brunch", 29.45), ("monthly groceries", 84.70),
        ]
        created = []
        today = date.today()
        for index, (description, amount) in enumerate(purchases):
            merchant = merchants[index % len(merchants)]
            created.append(client.create_purchase(
                ids[1], _id(merchant), amount, description, today - timedelta(days=(index * 2) % 30),
            ))
        return {"created": len(created), "purchases": created}
    except HTTPException:
        raise
    except NessieError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Nessie seeding failed: {exc}") from exc


# Preserve the legacy routes above and expose main's authenticated API on the
# same application, regardless of which documented entry point is used.
from backend.routers import auth, nessie, predictions, receipts, shopping, shopping_list, spending

for api_router in (auth.router, nessie.router, predictions.router, receipts.router,
                   shopping.router, shopping_list.router, spending.router):
    app.include_router(api_router)
