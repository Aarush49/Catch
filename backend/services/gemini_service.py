"""Gemini receipt extraction and short financial explanations."""

import os
import re

from google import genai
from google.genai import types

from backend.models import ParsedReceipt


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=api_key)


def parse_receipt(image_bytes: bytes, mime_type: str) -> ParsedReceipt:
    client = _client()
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=[
            "Read this receipt. Return the store, purchase date as YYYY-MM-DD, total, and each purchased item with its printed name, line total price, and one category from: groceries, produce, dairy, meat_seafood, bakery, beverages, snacks, household, personal_care, health, electronics, clothing, restaurant, entertainment, transportation, utilities, other. Do not include subtotal or tax as items. Never invent items or prices. Return only structured JSON.",
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=ParsedReceipt.model_json_schema(),
            temperature=0.1,
        ),
    )
    if not response.text:
        raise ValueError("Gemini returned an empty receipt response.")
    return ParsedReceipt.model_validate_json(response.text)


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
        response = _client().models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=(
                "Write exactly one plain, friendly sentence for a consumer finance app. "
                f"Say that {subject} "
                f"could grow to about {amount} in {years} years at {annual_return:.1%} annual return. "
                "Do not add advice, caveats, or other numbers."
            ),
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=60),
        )
        text = (response.text or "").strip().replace("\n", " ")
        if text:
            text = text.strip('" ')
            sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
            return sentence if sentence.endswith((".", "!", "?")) else f"{sentence}."
    except Exception:
        pass
    return fallback
