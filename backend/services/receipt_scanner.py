import io
import os
import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Literal

import httpx
from PIL import Image

Category = Literal["Groceries", "Dining", "Household", "Health", "Transport", "Other"]

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
        # API Ninjas returns text boxes, often one word per box. Reconstruct
        # rows from their bounding boxes so prices stay beside item names.
        blocks = [block for block in result if block.get("text", "").strip() and block.get("bounding_box")]
        blocks.sort(key=lambda block: ((block["bounding_box"]["y1"] + block["bounding_box"]["y2"]) / 2,
                                       block["bounding_box"]["x1"]))
        rows: list[dict[str, object]] = []
        for block in blocks:
            box = block["bounding_box"]
            cy = (box["y1"] + box["y2"]) / 2
            height = max(box["y2"] - box["y1"], 1)
            row = next((candidate for candidate in rows
                        if abs(cy - float(candidate["cy"])) <= max(5, min(height, float(candidate["height"])) * .65)), None)
            if row is None:
                rows.append({"cy": cy, "height": height, "words": [(box["x1"], block["text"].strip())]})
            else:
                row["words"].append((box["x1"], block["text"].strip()))
                row["cy"] = (float(row["cy"]) + cy) / 2
        text = "\n".join(" ".join(word for _, word in sorted(row["words"])) for row in rows)
        if not text:
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


def _local_parse_receipt(text: str) -> dict:
    """Best-effort fallback for when the receipt structuring model is unavailable."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    excluded = ("subtotal", "tax", "total", "change", "cash", "debit", "credit", "payment", "account",
                "approval", "network", "barcode", "items sold", "tender", "balance", "discount", "savings")
    summary_prefixes = ("subt", "total", "tax", "salestax", "amountdue", "balance", "change", "cash",
                        "debit", "credit", "payment", "tender", "discount", "savings", "itemssold", "eft")
    amount = re.compile(r"(?:\$\s*)?(\d{1,6}\.\d{2})\s*[A-Z0-9]?$", re.IGNORECASE)

    def has_total_marker(value: str) -> bool:
        normalized = re.sub(r"[^a-z]", "", value.lower())
        if any(normalized.startswith(prefix) for prefix in ("total", "subt", "grandtotal")):
            return True
        # OCR commonly swaps/drops one character (for example TOTHL).
        tokens = re.findall(r"[a-z]+", value.lower())
        candidates = tokens + ([normalized] if normalized not in tokens else [])
        return any(
            len(candidate) in range(4, 10)
            and SequenceMatcher(None, candidate, label).ratio() >= .78
            for candidate in candidates for label in ("total", "subtotal")
        )

    # Receipt summaries come after the purchased items. Once the total area
    # starts, none of its amounts should be interpreted as another item.
    summary_start = next(
        (index for index, line in enumerate(lines)
         if (match := amount.search(line)) and has_total_marker(line[:match.start()])),
        len(lines),
    )
    items = []
    for line_index, line in enumerate(lines[:summary_start]):
        match = amount.search(line)
        if not match:
            continue
        name = line[:match.start()].strip(" -:*$")
        if len(name) < 2 and line_index > 0:
            # OCR can put the item's name/UPC and its price in adjacent rows.
            previous = lines[line_index - 1]
            if (not amount.search(previous) and not any(term in previous.lower() for term in excluded)
                    and not has_total_marker(previous)):
                name = previous
        name = re.sub(r"\b\d{6,}\b", "", name).strip(" -:*$")
        name = re.sub(r"\s+[A-Z]$", "", name, flags=re.IGNORECASE).strip()
        if (len(name) < 2 or any(term in line.lower() for term in excluded)
                or any(re.sub(r"[^a-z]", "", name.lower()).startswith(prefix) for prefix in summary_prefixes)
                or has_total_marker(name)):
            continue
        price = float(match.group(1))
        if price <= 0:
            continue
        lowered = name.lower()
        category: Category = "Other"
        if any(word in lowered for word in ("bread", "milk", "egg", "produce", "meat", "cheese", "grocery")):
            category = "Groceries"
        elif any(word in lowered for word in ("restaurant", "cafe", "coffee", "pizza", "burger", "deli")):
            category = "Dining"
        elif any(word in lowered for word in ("soap", "paper", "clean", "detergent", "household")):
            category = "Household"
        elif any(word in lowered for word in ("pharmacy", "medicine", "health", "vitamin")):
            category = "Health"
        items.append({"name": name, "quantity": 1, "price": price, "category": category})

    def labeled_amount(label: str) -> float | None:
        for line in reversed(lines):
            if label in line.lower():
                match = amount.search(line)
                if match:
                    return float(match.group(1))
        return None

    date_value = None
    for line in lines:
        match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", line)
        if match:
            month, day, year = map(int, match.groups())
            year += 2000 if year < 100 else 0
            try:
                date_value = datetime(year, month, day).date().isoformat()
                break
            except ValueError:
                pass
    merchant = next((line for line in lines[:8] if not any(term in line.lower() for term in excluded)
                     and not amount.search(line) and len(line) >= 3), "Unknown store")
    printed_subtotal = labeled_amount("subtotal")
    # If OCR misses or clips the printed subtotal label, the sum of purchased
    # item lines is the pre-tax subtotal. It is metadata, never another item.
    subtotal = printed_subtotal if printed_subtotal is not None else round(sum(item["price"] for item in items), 2)
    tax = labeled_amount("tax")
    if not items:
        raise ValueError("The receipt text was extracted, but its items could not be identified. Please retry or enter it manually.")
    return {
        "merchant": merchant, "purchased_at": date_value, "currency": "USD", "items": items,
        # In this app's receipt workflow, the subtotal is the authoritative
        # saved total. Keep tax as separate metadata and never add it to total.
        "subtotal": subtotal, "tax": tax, "total": subtotal,
        "needs_review": True,
        "review_reason": ("Subtotal was estimated from the item prices because the printed subtotal was unreadable. "
                          "It is saved as the total without adding tax. Please verify the result." if printed_subtotal is None else
                          "The subtotal is saved as the total without adding tax. Please verify the result."),
    }

def scan_image(image: bytes, mime_type: str) -> dict:
    """OCR with API Ninjas, then parse receipt fields locally without Gemini."""
    recognized_text = _ocr_receipt(image)
    return _local_parse_receipt(recognized_text)
