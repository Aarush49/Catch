from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.services.carbon import estimate_carbon
from backend.services.gemini_service import GeminiReceiptError, parse_receipt
from backend.routers.auth import current_user
from backend.services.sqlite_store import get_receipt, list_receipts, save_receipt


router = APIRouter(prefix="/api/receipts", tags=["receipts"])
MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/scan", status_code=201)
def scan_receipt(file: UploadFile = File(...), user=Depends(current_user)) -> dict[str, Any]:
    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP receipt image.")
    image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 15 MB or smaller.")
    try:
        parsed = parse_receipt(image_bytes, mime_type)
    except RuntimeError as exc:
        detail = str(exc)
        if "GEMINI_API_KEY" in detail:
            detail = "Receipt scanning is not configured. Set GEMINI_API_KEY in the backend .env file and restart the API."
        raise HTTPException(status_code=503, detail=detail) from None
    except GeminiReceiptError as exc:
        if exc.status_code == 429:
            raise HTTPException(status_code=503, detail="Gemini is rate limited or out of quota. Wait a moment and check your AI Studio quota.") from None
        if exc.status_code in {401, 403}:
            raise HTTPException(status_code=503, detail="Gemini rejected the API key or this model is not enabled for the key.") from None
        if exc.status_code == 404:
            raise HTTPException(status_code=503, detail="Gemini could not find the configured model. Set GEMINI_MODEL=gemini-3.8-flash in the backend .env file and restart the API.") from None
        raise HTTPException(status_code=502, detail=f"Gemini rejected the scan request (HTTP {exc.status_code}); this is an API request/configuration issue, not an unclear-photo result.") from None
    except Exception:
        raise HTTPException(status_code=502, detail="Gemini did not complete the receipt scan. Check the API key, quota, and network connection, then retry. If those are working, take a brighter, closer photo.") from None

    receipt = parsed.model_dump()
    receipt["items"] = [
        {**item, "carbon_kg_co2e": estimate_carbon(item["price"], item["category"])}
        for item in receipt["items"]
    ]
    if receipt["total"] is None:
        receipt["total"] = sum((item["price"] for item in receipt["items"]), start=0)
    return save_receipt(user["id"], receipt)


@router.get("")
def receipts(user=Depends(current_user)) -> list[dict[str, Any]]:
    return list_receipts(user["id"])


@router.get("/{receipt_id}")
def receipt(receipt_id: UUID, user=Depends(current_user)) -> dict[str, Any]:
    result = get_receipt(user["id"], str(receipt_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return result
