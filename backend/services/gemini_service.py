"""Gemini receipt extraction and short financial explanations."""

import os
import re
import json
from io import BytesIO
from datetime import date, datetime

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:  # Keep the API importable until updated requirements are installed.
    Image = ImageEnhance = ImageFilter = ImageOps = None

from google import genai
from google.genai import errors, types

from backend.models import ParsedReceipt


# Gemini's structured-output API accepts a JSON Schema subset. Pydantic's
# Decimal/Optional schema includes anyOf, references, and format keywords that
# Gemini may reject; send a deliberately simple schema and validate its result
# with Pydantic afterward.
_RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "store": {"type": "string"},
        "date": {"type": "string"},
        "total": {"type": "number"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "groceries", "produce", "dairy", "meat_seafood", "bakery",
                            "beverages", "snacks", "household", "personal_care", "health",
                            "electronics", "clothing", "restaurant", "entertainment",
                            "transportation", "utilities", "other",
                        ],
                    },
                },
                "required": ["name", "price", "category"],
            },
        },
    },
    "required": ["store", "date", "total", "items"],
}


class GeminiReceiptError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Gemini receipt request failed with status {status_code}.")


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=api_key)


def parse_receipt(image_bytes: bytes, mime_type: str) -> ParsedReceipt:
    client = _client()
    prepared, prepared_type, sections = _prepare_receipt_images(image_bytes, mime_type)
    prompt = (
        "Transcribe this receipt carefully. Return store, purchase date (YYYY-MM-DD), total, and every item whose name and line price are readable, with one category from: groceries, produce, dairy, meat_seafood, bakery, beverages, snacks, household, personal_care, health, electronics, clothing, restaurant, entertainment, transportation, utilities, other. "
        "Always include store, date, total, and items. Use an empty string for an unreadable store/date, 0 for an unreadable total, and an empty items array if the paper has no itemized purchases. "
        "Do not mistake card authorization details for products. The image may be slightly blurry: inspect each line and use context only to interpret visible characters. Do not reject the whole image because some text is unclear. Skip only unreadable lines; do not guess names or prices. Do not count subtotal, tax, tip, or change as items. Return the best partial result as structured JSON."
    )
    best = _try_receipt_pass(client, prompt, prepared, prepared_type)
    images: list[tuple[bytes, str]] = []
    # A phone photo of a long receipt often makes the item text too small in a
    # full-page view. Ask Gemini to read enlarged sections when the first pass
    # found nothing or only a single line.
    receipt_header_is_complete = bool(best.store and best.total is not None)
    if sections and len(best.items) < 2 and (best.items or not receipt_header_is_complete):
        images.extend((section, "image/jpeg") for section in sections)
    if not best.items and prepared != image_bytes:
        images.append((image_bytes, mime_type))
    for data, content_type in images:
        try:
            parsed = _try_receipt_pass(client, prompt, data, content_type)
            known = {(item.name.casefold().strip(), str(item.price)) for item in best.items}
            extra = [item for item in parsed.items if (item.name.casefold().strip(), str(item.price)) not in known]
            best = best.model_copy(update={
                "store": best.store or parsed.store,
                "date": best.date or parsed.date,
                "total": best.total or parsed.total,
                "items": [*best.items, *extra],
            })
        except Exception:
            # Keep a successful full-image result if a crop happens to be invalid.
            if not best.items:
                raise
    return best


def _try_receipt_pass(client: genai.Client, prompt: str, data: bytes, mime_type: str) -> ParsedReceipt:
    model = _model_name()
    config = {
        "response_mime_type": "application/json",
        "response_json_schema": _RECEIPT_SCHEMA,
    }
    # Gemini 3+ rejects legacy sampling controls such as temperature.
    if not model.startswith(("gemini-3", "gemini-4")):
        config["temperature"] = 0.1
    try:
        response = client.models.generate_content(
            model=model,
            contents=[prompt, types.Part.from_bytes(data=data, mime_type=mime_type)],
            config=types.GenerateContentConfig(**config),
        )
    except errors.APIError as exc:
        raise GeminiReceiptError(exc.code if isinstance(exc.code, int) else 502) from None
    if not response.text:
        return ParsedReceipt()
    payload = json.loads(response.text)
    receipt_date = payload.get("date")
    if receipt_date:
        # Common US receipt format is MM/DD/YYYY; normalize it before Pydantic.
        try:
            if "/" in receipt_date:
                payload["date"] = datetime.strptime(receipt_date, "%m/%d/%Y").date().isoformat()
            else:
                payload["date"] = date.fromisoformat(receipt_date).isoformat()
        except ValueError:
            payload["date"] = None
    else:
        payload["date"] = None
    payload["store"] = payload.get("store") or None
    if not payload.get("total"):
        payload["total"] = None
    return ParsedReceipt.model_validate(payload)


def _prepare_receipt_images(data: bytes, mime_type: str) -> tuple[bytes, str, list[bytes]]:
    """Correct orientation, boost text contrast, and create enlarged receipt crops."""
    if Image is None:
        return data, mime_type, []
    try:
        image = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
        # Normalize very large camera photos too; APIs have per-image limits.
        if max(image.size) > 4096:
            scale = 4096 / max(image.size)
            image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
        if max(image.size) < 2800:
            scale = min(3.0, 2800 / max(image.size))
            image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.25)
        image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3))

        def encode(part: Image.Image) -> bytes:
            out = BytesIO()
            part.save(out, format="JPEG", quality=94, optimize=True)
            return out.getvalue()

        sections: list[bytes] = []
        # Vertical receipts have very small print when sent as one image.
        if image.height >= image.width * 1.25 and image.height >= 1600:
            third = image.height // 3
            for index in range(3):
                top = max(0, index * third - (80 if index else 0))
                bottom = min(image.height, (index + 1) * third + (80 if index < 2 else 0))
                crop = image.crop((0, top, image.width, bottom))
                crop_scale = min(1.6, 2600 / max(crop.size))
                if crop_scale > 1:
                    crop = crop.resize((round(crop.width * crop_scale), round(crop.height * crop_scale)), Image.Resampling.LANCZOS)
                sections.append(encode(crop))
        return encode(image), "image/jpeg", sections
    except Exception:
        return data, mime_type, []


def explain_future_savings(
    future_savings: float,
    years: int,
    annual_return: float,
    recurring: bool = False,
    alternative: bool = False,
) -> str:
    """Ask Gemini for one plain sentence; use a deterministic fallback if unavailable."""
    amount = f"${future_savings:,.2f}"
    subject = (
        "choosing the lower-cost recurring option" if recurring and alternative else
        "skipping these recurring purchases" if recurring else
        "choosing the lower-cost option" if alternative else
        "skipping this purchase"
    )
    fallback = f"By {subject}, you could have about {amount} after {years} years."
    try:
        model = _model_name()
        config = {"max_output_tokens": 60}
        if not model.startswith(("gemini-3", "gemini-4")):
            config["temperature"] = 0.2
        response = _client().models.generate_content(
            model=model,
            contents=(
                "Write exactly one plain, friendly sentence for a consumer finance app. "
                f"Say that {subject} "
                f"could grow to about {amount} in {years} years at {annual_return:.1%} annual return. "
                "Do not add advice, caveats, or other numbers."
            ),
            config=types.GenerateContentConfig(**config),
        )
        text = (response.text or "").strip().replace("\n", " ")
        if text:
            text = text.strip('" ')
            sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
            return sentence if sentence.endswith((".", "!", "?")) else f"{sentence}."
    except Exception:
        pass
    return fallback
