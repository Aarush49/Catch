from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.carbon import estimate_carbon
from backend.services.gemini_service import parse_receipt
from backend.services.memory_store import get_receipt, list_receipts, save_receipt


router = APIRouter(prefix="/api/receipts", tags=["receipts"])
MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/scan", status_code=201)
def scan_receipt(file: UploadFile = File(...)) -> dict[str, Any]:
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
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=502, detail="Gemini could not read this receipt. Try a clearer image.") from None

    receipt = parsed.model_dump()
    receipt["items"] = [
        {**item, "carbon_kg_co2e": estimate_carbon(item["price"], item["category"])}
        for item in receipt["items"]
    ]
    if receipt["total"] is None:
        receipt["total"] = sum((item["price"] for item in receipt["items"]), start=0)
    return save_receipt(receipt)


@router.get("")
def receipts() -> list[dict[str, Any]]:
    return list_receipts()


@router.get("/{receipt_id}")
def receipt(receipt_id: UUID) -> dict[str, Any]:
    result = get_receipt(receipt_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return result
