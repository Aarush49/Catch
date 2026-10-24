"""Supabase-backed storage with the existing Python/API response shapes."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from uuid import UUID

from pydantic import ValidationError

from app.database import DatabaseError, rpc
from app.models import ParsedReceipt, ReceiptItem

DEMO_USERNAME = "ripple-demo"


class InvalidReceiptError(ValueError):
    pass


def _uuid(value: UUID | str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A valid UUID is required.") from None


def _owner(user_id: UUID | str | None) -> str | None:
    return str(_uuid(user_id)) if user_id is not None else None


def _timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("A timestamp must include its timezone.")
    return result.astimezone(timezone.utc)


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    # RPCs explicitly return NUMERIC as text, avoiding the SDK JSON decoder's
    # float conversion and irreversible precision loss on high-precision prices.
    if isinstance(value, (bool, float)):
        raise ValueError("RPC monetary values must be decimal strings.")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("A finite decimal is required.")
    return result


def _user(data: dict) -> dict[str, Any]:
    if not isinstance(data["username"], str) or not data["username"].strip():
        raise ValueError("Invalid username")
    return {"id": _uuid(data["id"]), "username": data["username"], "created_at": _timestamp(data["created_at"])}


def _item(data: dict) -> dict[str, Any]:
    item = ReceiptItem.model_validate({
        "raw_name": data["raw_name"], "full_name": data["full_name"], "category": data["category"],
        "quantity": _decimal(data["quantity"]), "unit_price": _decimal(data["unit_price"]),
        "total_price": _decimal(data["total_price"]),
    })
    return {
        "id": _uuid(data["id"]), "receipt_id": _uuid(data["receipt_id"]), **item.model_dump(),
        "purchased_at": _timestamp(data["purchased_at"]), "created_at": _timestamp(data["created_at"]),
    }


def _receipt(data: dict) -> dict[str, Any]:
    raw = ParsedReceipt.model_validate(data["raw_json"]).model_dump()
    total = _decimal(data["total"])
    if total is None:
        raise ValueError("Receipt total is required")
    return {
        "id": _uuid(data["id"]), "store_name": data["store_name"],
        "purchase_date": date.fromisoformat(data["purchase_date"]) if data["purchase_date"] else None,
        "subtotal": _decimal(data["subtotal"]), "tax": _decimal(data["tax"]), "total": total,
        "raw_json": raw, "created_at": _timestamp(data["created_at"]),
        "items": [_item(row) for row in data["items"]], "warnings": raw["warnings"],
    }


def _decode(convert: Callable, data):
    try:
        return convert(data)
    except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
        raise DatabaseError("Supabase returned invalid receipt storage data.") from None


def _rows(data, convert: Callable) -> list:
    if not isinstance(data, list):
        raise DatabaseError("Supabase returned an invalid collection response.")
    return [_decode(convert, row) for row in data]


def _validated_receipt(receipt: dict[str, Any]) -> ParsedReceipt:
    try:
        parsed = ParsedReceipt.model_validate(receipt)
        for item in parsed.items:
            if (
                not item.raw_name.strip() or not item.full_name.strip()
                or item.quantity <= 0 or item.total_price < 0
                or (item.unit_price is not None and item.unit_price < 0)
            ):
                raise ValueError
        return parsed
    except (ValidationError, ValueError, TypeError):
        raise InvalidReceiptError(
            "Invalid receipt: check required fields, categories, finite nonnegative prices, and positive quantities."
        ) from None


def get_or_create_user(username: str) -> dict[str, Any]:
    if not isinstance(username, str) or not 1 <= len(username.strip()) <= 100:
        raise ValueError("Username must contain 1 to 100 characters.")
    return _decode(_user, rpc("ripple_get_or_create_user", {"p_username": username.strip()}))


def get_user(user_id: UUID | str) -> dict[str, Any] | None:
    data = rpc("ripple_get_user", {"p_user_id": str(_uuid(user_id))})
    return _decode(_user, data) if data is not None else None


def save_receipt(receipt: dict[str, Any], user_id: UUID | str | None = None) -> dict[str, Any]:
    parsed = _validated_receipt(receipt)
    # A single RPC creates the demo user (if needed), receipt, and all lines.
    # Keep the original process-local date fallback for undated receipts.
    data = rpc("ripple_save_receipt", {
        "p_receipt": parsed.model_dump(mode="json"), "p_user_id": _owner(user_id),
        "p_fallback_date": date.today().isoformat(),
    })
    return _decode(_receipt, data)


def list_receipts(user_id: UUID | str | None = None) -> list[dict[str, Any]]:
    return _rows(rpc("ripple_receipts", {"p_user_id": _owner(user_id)}), _receipt)


def get_receipt(receipt_id: UUID, user_id: UUID | str | None = None) -> dict[str, Any] | None:
    data = rpc("ripple_receipts", {"p_user_id": _owner(user_id), "p_receipt_id": str(_uuid(receipt_id))})
    rows = _rows(data, _receipt)
    if len(rows) > 1:
        raise DatabaseError("Supabase returned an invalid receipt lookup response.")
    return rows[0] if rows else None


def list_receipt_items(receipt_id: UUID, user_id: UUID | str | None = None) -> list[dict[str, Any]]:
    receipt = get_receipt(receipt_id, user_id)
    return receipt["items"] if receipt else []


def list_items(
    category: str | None, start: date | None, end: date | None,
    user_id: UUID | str | None = None,
) -> list[dict[str, Any]]:
    if start and end and start > end:
        raise ValueError("start must be on or before end.")
    data = rpc("ripple_items", {
        "p_category": category, "p_start": start.isoformat() if start else None,
        "p_end": end.isoformat() if end else None, "p_user_id": _owner(user_id),
    })
    return _rows(data, _item)


def spending_summary(period: str, user_id: UUID | str | None = None) -> dict[str, Any]:
    if period not in {"week", "month", "all"}:
        raise ValueError("period must be week, month, or all.")
    data = rpc("ripple_spending_summary", {"p_period": period, "p_user_id": _owner(user_id)})

    def convert(value):
        if value["period"] != period:
            raise ValueError("Unexpected period")
        return {
            "period": period,
            "by_category": [{"category": row["category"], "total": _decimal(row["total"])} for row in value["by_category"]],
            "by_day": [{"day": date.fromisoformat(row["day"]), "total": _decimal(row["total"])} for row in value["by_day"]],
        }
    return _decode(convert, data)


def get_demo_ids() -> tuple[str, str] | None:
    data = rpc("ripple_demo_ids")
    if data is None:
        return None

    def convert(value):
        if not all(isinstance(value[key], str) and value[key].strip() for key in ("customer_id", "account_id")):
            raise ValueError("Invalid demo IDs")
        return value["customer_id"], value["account_id"]
    return _decode(convert, data)


def set_demo_ids(customer_id: str, account_id: str) -> None:
    if not isinstance(customer_id, str) or not customer_id.strip() or not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("Customer and account IDs must be nonempty strings.")
    result = rpc("ripple_demo_ids", {"p_customer_id": customer_id, "p_account_id": account_id})
    if result != {"customer_id": customer_id, "account_id": account_id}:
        raise DatabaseError("Supabase did not confirm the saved demo IDs.")
