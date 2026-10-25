import logging
import os
from datetime import date
from typing import Literal

from google import genai
from google.genai import types
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

def scan_image(image: bytes, mime_type: str) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Receipt scanning is not configured.")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30_000))
    error = None
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
                contents=[PROMPT, types.Part.from_bytes(data=image, mime_type=mime_type)],
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
    raise RuntimeError("Gemini could not read the receipt. Please retry; the backend log shows the cause.") from error
