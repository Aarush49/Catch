import logging
import os
import io
import time
from datetime import date
from typing import Literal

import httpx
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel, Field, field_validator

Category = Literal["Groceries", "Dining", "Household", "Health", "Transport", "Other"]

class ScannedItem(BaseModel):
    name: str | None = None
    quantity: float | None = 1
    price: float | None = None
    category: Category = "Other"

class ScannedReceipt(BaseModel):
    merchant: str | None = None
    purchased_at: date | None = None
    currency: str | None = None
    items: list[ScannedItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None

    @field_validator("subtotal", "tax", "total")
    @classmethod
    def nonnegative(cls, value):
        return None if value is None else max(0, float(value))

PROMPT = """Read this receipt without inventing any items or prices. Return merchant, purchased_at as YYYY-MM-DD or null, currency, subtotal, tax, total, and purchased line items with name, quantity, line-total price, and category. Categories are exactly Groceries, Dining, Household, Health, Transport, Other. Expand abbreviated names when obvious; otherwise keep a readable cleaned version. Ignore payment/card lines, loyalty points, barcodes, subtotals, taxes, and totals as items. Use null for unreadable receipt fields. If this is not a purchase receipt, return no merchant, no total, and an empty items list."""

class OCRConfigurationError(RuntimeError):
    pass


def _fit_api_ninjas_free_limit(image: bytes) -> bytes:
    """Encode a readable JPEG within API Ninjas' 200 KB free image limit."""
    try:
        with Image.open(io.BytesIO(image)) as source:
            source = source.convert("RGB")
            source.thumbnail((1800, 1800))
            for quality in (88, 80, 72, 64, 56, 48, 40):
                output = io.BytesIO()
                source.save(output, format="JPEG", quality=quality, optimize=True)
                encoded = output.getvalue()
                if len(encoded) <= 200 * 1024:
                    return encoded
            # Reduce dimensions as a last resort while retaining legible receipt text.
            for width in (1500, 1300, 1100, 900):
                resized = source.copy()
                resized.thumbnail((width, width))
                output = io.BytesIO()
                resized.save(output, format="JPEG", quality=55, optimize=True)
                encoded = output.getvalue()
                if len(encoded) <= 200 * 1024:
                    return encoded
    except Exception as exc:
        raise ValueError("This image could not be prepared for receipt scanning.") from exc
    raise ValueError("This receipt image is too detailed to fit the OCR service's 200 KB free limit. Try a clearer, closer photo.")


def _ocr_receipt(image: bytes) -> str:
    """Extract receipt text with API Ninjas' Image to Text endpoint."""
    api_key = os.getenv("API_NINJAS_KEY", "").strip()
    if not api_key:
        raise OCRConfigurationError(
            "Receipt OCR is not configured. Add API_NINJAS_KEY to the project-root .env."
        )
    encoded = _fit_api_ninjas_free_limit(image)
    try:
        response = httpx.post("https://api.api-ninjas.com/v1/imagetotext",
                              headers={"X-Api-Key": api_key},
                              files={"image": ("receipt.jpg", encoded, "image/jpeg")}, timeout=30)
        response.raise_for_status()
        result = response.json()
        text = "\n".join(block.get("text", "").strip() for block in result if block.get("text", "").strip())
        if not text:
            raise ValueError("No readable receipt text was found. Try a sharper, brighter image.")
        return text
    except httpx.TimeoutException:
        raise RuntimeError("Receipt OCR timed out. Please retry.") from None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise OCRConfigurationError("API Ninjas rejected the key. Check API_NINJAS_KEY in the project-root .env.") from None
        if exc.response.status_code == 413:
            raise ValueError("The receipt image exceeds API Ninjas' 200 KB free image limit.") from None
        raise RuntimeError(f"API Ninjas OCR returned HTTP {exc.response.status_code}. Check its free-tier quota and try again.") from None
    except httpx.HTTPError:
        raise RuntimeError("Receipt OCR could not reach API Ninjas. Check your network and retry.") from None

def scan_image(image: bytes, mime_type: str) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Receipt scanning is not configured.")
    timeout_ms = max(30_000, int(os.getenv("GEMINI_TIMEOUT_MS", "120000")))
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=timeout_ms))
    recognized_text = _ocr_receipt(image)
    contents = [f"{PROMPT}\n\nOCR text extracted from the receipt image:\n---\n{recognized_text}\n---"]
    error = None
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
                contents=contents,
                config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json", response_schema=ScannedReceipt),
            )
            parsed = ScannedReceipt.model_validate_json(response.text or "{}")
            parsed.items = [item for item in parsed.items if item.name and item.price is not None and item.price >= 0]
            if not parsed.items and not parsed.merchant and parsed.total is None:
                raise ValueError("The image does not appear to contain a readable receipt.")
            item_sum = sum((item.price or 0) for item in parsed.items)
            baseline = parsed.subtotal if parsed.subtotal is not None else item_sum
            difference = abs(item_sum - baseline)
            needs_review = bool(baseline and difference / baseline > .05)
            result = parsed.model_dump(mode="json")
            result.update(needs_review=needs_review, review_reason=(f"Item totals differ from the subtotal by ${difference:.2f}." if needs_review else None))
            return result
        except ValueError:
            raise
        except Exception as exc:
            error = exc
            logging.getLogger(__name__).warning("Gemini scan attempt %d failed: %s: %s",
                                                attempt + 1, type(exc).__name__, str(exc)[:300])
            if attempt:
                break
            # Give transient upstream deadline/load errors a moment to clear.
            time.sleep(1.5)
    raise RuntimeError("Gemini could not read the receipt. Please retry; the backend log shows the cause.") from error
