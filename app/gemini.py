import os
from decimal import Decimal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.models import ParsedReceipt

load_dotenv()

PROMPT = """Read this receipt image and return its data. Extract store name, purchase date in ISO YYYY-MM-DD format, subtotal, tax and total. For each purchased line item return raw_name exactly as printed, full_name expanded into the most likely human-readable product name (include brand and size if visible), category, quantity, unit_price and total_price. Categories must be one of: groceries, produce, dairy, meat_seafood, bakery, beverages, snacks, household, personal_care, health, electronics, clothing, restaurant, entertainment, transportation, other. Never invent items; skip unreadable lines. If unsure about a full name, use a cleaned-up raw name. Ignore subtotal, tax, payment, loyalty points and standalone discounts. Subtract a discount applying to an item from that item's total_price. Use null for unreadable receipt-level numeric values and an empty list for no readable items."""


def parse_receipt(image_bytes: bytes, mime_type: str) -> ParsedReceipt:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    last_error: Exception | None = None
    for attempt in range(2):
        prompt = PROMPT
        if attempt:
            prompt += " Your prior answer failed validation. Check all required fields, amounts, and category values carefully."
        try:
            response = client.models.generate_content(
                model=model,
                contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=ParsedReceipt.model_json_schema(),
                ),
            )
            if not response.text:
                raise ValueError("Gemini returned an empty response")
            parsed = ParsedReceipt.model_validate_json(response.text)
            if parsed.subtotal is not None:
                item_total = sum((item.total_price for item in parsed.items), Decimal("0"))
                if abs(item_total - parsed.subtotal) > Decimal("0.10"):
                    parsed.warnings.append(
                        f"Item totals ({item_total:.2f}) do not match subtotal ({parsed.subtotal:.2f})."
                    )
            return parsed
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not parse receipt after retry: {last_error}") from last_error
