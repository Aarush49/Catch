"""Receipt scanning: fast OCR path when the items add up, Gemini fallback when they don't."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from backend.services import gemini_service, receipt_scanner
from backend.services.supabase_jwt import require_supabase_user

CLEAN_OCR = "TRADER JOES\n10/24/2026\nBANANAS 2.18\nOAT MILK 4.19\nEGGS 6.99\nSUBTOTAL 13.36\nTAX 0.00\nTOTAL 13.36"
# Thermal receipt OCR where right-column prices were dropped and quantity lines look like items.
GARBLED_OCR = "RoadRanger\nDate: 10/24/2026\nHOSTESS BAG MNI\n1@ 4.59 each\nKELL P TRT SS\n1@ 1.99 each -1.48\nSUBTOTAL 7.09\nTOTAL 7.09"
ROAD_RANGER = {
    "store": "Road Ranger", "date": "2026-10-24", "subtotal": 7.09, "tax": 0,
    "items": [
        {"name": "HOSTESS BAG MNI", "quantity": 1, "line_total": 4.59, "category": "Groceries"},
        {"name": "KELL P TRT SS", "quantity": 1, "line_total": 1.99, "category": "Groceries"},
        {"name": "KELL P TRT SS", "quantity": 1, "line_total": 1.99, "category": "Groceries"},
        {"name": "POPTARTS 2/2.50", "quantity": 1, "line_total": -1.48, "category": "Groceries"},
    ],
}


def png(width=400, height=600) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def services(monkeypatch):
    """Fake OCR text and Gemini reply; record whether Gemini was asked."""
    state = {"ocr": CLEAN_OCR, "gemini": ROAD_RANGER, "gemini_calls": 0}

    def ocr(image):
        if isinstance(state["ocr"], Exception):
            raise state["ocr"]
        return state["ocr"]

    def read_receipt(image, mime_type):
        state["gemini_calls"] += 1
        if isinstance(state["gemini"], Exception):
            raise state["gemini"]
        return state["gemini"]

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-never-real")
    monkeypatch.setattr(receipt_scanner, "_ocr_receipt", ocr)
    monkeypatch.setattr(gemini_service, "read_receipt", read_receipt)
    return state


def test_receipt_that_adds_up_uses_ocr_only(services):
    result = receipt_scanner.scan_image(png(), "image/png")
    assert services["gemini_calls"] == 0
    assert [(item["name"], item["price"]) for item in result["items"]] == [("BANANAS", 2.18), ("OAT MILK", 4.19), ("EGGS", 6.99)]
    assert result["total"] == 13.36 and result["purchased_at"] == "2026-10-24"
    assert "_items_match_subtotal" not in result


def test_receipt_that_does_not_add_up_is_read_by_gemini_with_discounts_folded(services):
    services["ocr"] = GARBLED_OCR
    result = receipt_scanner.scan_image(png(), "image/png")
    assert services["gemini_calls"] == 1
    assert [item["price"] for item in result["items"]] == [4.59, 1.99, 0.51]
    assert result["total"] == result["subtotal"] == 7.09 == round(sum(item["price"] for item in result["items"]), 2)
    assert result["merchant"] == "Road Ranger" and result["purchased_at"] == "2026-10-24"
    assert "Gemini" in result["review_reason"] and "Discounts" in result["review_reason"]
    assert all(item["price"] >= 0 for item in result["items"])


def test_quantity_detail_lines_are_not_items():
    parsed = receipt_scanner._local_parse_receipt("SHOP\nCHIPS 2.00\n2 @ 1.00 each\nSUBTOTAL 2.00")
    assert [item["name"] for item in parsed["items"]] == ["CHIPS"]


def test_large_discount_spreads_over_earlier_items():
    result = receipt_scanner._receipt_from_gemini({"store": "S", "date": "", "subtotal": 0, "tax": 0, "items": [
        {"name": "A", "quantity": 1, "line_total": 3.00, "category": "Other"},
        {"name": "B", "quantity": 1, "line_total": 1.00, "category": "Other"},
        {"name": "Coupon", "quantity": 1, "line_total": -2.50, "category": "Other"},
    ]})
    assert [item["price"] for item in result["items"]] == [1.50, 0.0]
    assert result["total"] == 1.50 and result["purchased_at"] is None


def test_gemini_failure_does_not_offer_an_ocr_result_that_does_not_add_up(services):
    # The real Road Ranger OCR read the "SM/3.60Z" size as a $3.60 price; that must never reach review.
    services["ocr"], services["gemini"] = "SHOP\nKELL P TRT SS SM/3.60\nSUBTOTAL 7.09", RuntimeError("timeout")
    with pytest.raises(ValueError, match="try again"):
        receipt_scanner.scan_image(png(), "image/png")
    assert services["gemini_calls"] == 1


def test_sizes_glued_to_a_digit_are_not_prices():
    with pytest.raises(ValueError, match="items could not be identified"):
        receipt_scanner._local_parse_receipt("SHOP\nKELL P TRT SS SM/3.607\nSUBTOTAL 7.09")
    assert receipt_scanner._local_parse_receipt("SHOP\nMILK 4.19 F\nSUBTOTAL 4.19")["items"][0]["price"] == 4.19


def test_missing_ocr_key_still_scans_with_gemini(services):
    services["ocr"] = receipt_scanner.OCRConfigurationError("Add API_NINJAS_KEY")
    assert receipt_scanner.scan_image(png(), "image/png")["total"] == 7.09


def test_no_gemini_key_skips_the_fallback(services, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    services["ocr"] = "SHOP\nCHIPS 3.00\nSUBTOTAL 9.99"
    assert receipt_scanner.scan_image(png(), "image/png")["items"][0]["name"] == "CHIPS"
    assert services["gemini_calls"] == 0


def test_small_photos_are_enlarged_and_grayscale_for_ocr():
    prepared = Image.open(io.BytesIO(receipt_scanner._prepare_for_ocr(png(400, 600))))
    assert prepared.mode == "L" and max(prepared.size) == 1800
    assert receipt_scanner._prepare_for_ocr(b"not an image") == b"not an image"


def test_scan_endpoint_returns_the_review_payload_and_422_for_unreadable(services):
    app.dependency_overrides[require_supabase_user] = lambda: {"sub": "user-1"}
    try:
        client = TestClient(app)
        ok = client.post("/receipts/scan", files={"file": ("r.png", png(), "image/png")})
        assert ok.status_code == 200 and ok.json()["total"] == 13.36
        services["ocr"], services["gemini"] = "SHOP", RuntimeError("down")
        bad = client.post("/receipts/scan", files={"file": ("r.png", png(), "image/png")})
        assert bad.status_code == 422
    finally:
        app.dependency_overrides.pop(require_supabase_user, None)


@pytest.fixture
def gemini_calls(monkeypatch):
    """Fake Gemini client for read_receipt; `errors` maps a model name to the exception it raises."""
    from types import SimpleNamespace
    state = SimpleNamespace(calls=[], errors={})

    def generate_content(model, contents, config):
        state.calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        if model in state.errors:
            raise state.errors[model]
        return SimpleNamespace(text='{"store": "S", "date": "", "subtotal": 1, "tax": 0, "items": []}')

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-never-real")
    monkeypatch.delenv("GEMINI_RECEIPT_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_RECEIPT_BACKUP_MODEL", raising=False)
    monkeypatch.setattr(gemini_service.genai, "Client", lambda api_key: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    return state


def test_gemini_reads_receipts_carefully_on_a_shrunk_photo(gemini_calls):
    from google.genai import types
    assert gemini_service.read_receipt(png(2160, 2880), "image/png")["store"] == "S"
    call = gemini_calls.calls[0]
    assert len(gemini_calls.calls) == 1 and call.model == "gemini-3.5-flash"
    assert call.config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert call.config.http_options.timeout == gemini_service.RECEIPT_TIMEOUT_MS and call.config.http_options.retry_options.attempts == 1
    sent = Image.open(io.BytesIO(call.contents[1].inline_data.data))
    assert max(sent.size) == gemini_service.RECEIPT_MAX_SIDE and call.contents[1].inline_data.mime_type == "image/jpeg"


def test_busy_model_falls_back_to_the_backup(gemini_calls):
    from google.genai import errors
    gemini_calls.errors["gemini-3.5-flash"] = errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    assert gemini_service.read_receipt(png(), "image/png")["store"] == "S"
    assert [call.model for call in gemini_calls.calls] == ["gemini-3.5-flash", "gemini-3.7-flash"]


def test_timeout_does_not_wait_for_a_second_model(gemini_calls):
    gemini_calls.errors["gemini-3.5-flash"] = TimeoutError("read timed out")
    with pytest.raises(TimeoutError):
        gemini_service.read_receipt(png(), "image/png")
    assert [call.model for call in gemini_calls.calls] == ["gemini-3.5-flash"]
