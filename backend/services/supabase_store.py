"""Supabase persistence for main's authenticated API; no local database fallback."""

import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.database import DatabaseConstraintError, DatabaseError, rpc
from app.models import ParsedReceipt
from app.storage import _decimal, _decode, _timestamp, _uuid
from backend.models import ShoppingListItemCreate


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000).hex()


def _confirmed(result) -> None:
    if not isinstance(result, dict) or result.get("status") != "ok":
        raise DatabaseError("Supabase did not confirm the database write.")


def create_user(email: str, password: str) -> dict:
    salt = secrets.token_bytes(16)
    try:
        result = rpc("ripple_create_account", {
            "p_email": email.strip().lower(), "p_salt": salt.hex(),
            "p_password_hash": _hash(password, salt),
        })
    except DatabaseConstraintError as exc:
        if exc.code == "23505":
            raise ValueError("An account with this email already exists.") from None
        raise
    return _decode(_account, result)


def _account(data: dict) -> dict:
    if not isinstance(data["email"], str) or not data["email"]:
        raise ValueError("Invalid account")
    return {"id": str(_uuid(data["id"])), "email": data["email"]}


def authenticate(email: str, password: str) -> dict | None:
    record = rpc("ripple_auth_record", {"p_email": email.strip().lower()})
    if record is None:
        _hash(password, bytes(16))
        return None

    def verify(data):
        expected = _hash(password, bytes.fromhex(data["salt"]))
        return _account(data) if secrets.compare_digest(data["password_hash"], expected) else None
    return _decode(verify, record)


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(36)
    _confirmed(rpc("ripple_create_session", {
        "p_user_id": str(_uuid(user_id)), "p_token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "p_expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }))
    return token


def session_user(token: str) -> dict | None:
    data = rpc("ripple_session_user", {"p_token_hash": hashlib.sha256(token.encode()).hexdigest()})
    return _decode(_account, data) if data is not None else None


def delete_session(token: str) -> None:
    _confirmed(rpc("ripple_delete_session", {"p_token_hash": hashlib.sha256(token.encode()).hexdigest()}))


def _receipt(data: dict) -> dict:
    return {
        "id": str(_uuid(data["id"])), "store": data["store_name"],
        "date": date.fromisoformat(data["purchase_date"]) if data["purchase_date"] else None,
        "total": _decimal(data["total"]), "created_at": _timestamp(data["created_at"]),
        "items": [{
            "id": str(_uuid(item["id"])), "receipt_id": str(_uuid(item["receipt_id"])),
            "name": item["full_name"], "price": _decimal(item["total_price"]),
            "category": item["category"], "carbon_kg_co2e": _decimal(item["carbon_kg_co2e"]),
        } for item in data["items"]],
    }


def _rows(data, convert) -> list:
    if not isinstance(data, list):
        raise DatabaseError("Supabase returned an invalid collection response.")
    return [_decode(convert, row) for row in data]


def save_receipt(user_id: str, receipt: dict) -> dict:
    # Translate main's receipt shape to the existing atomic receipt RPC.
    parsed = ParsedReceipt.model_validate({
        "store_name": receipt.get("store"), "purchase_date": receipt.get("date"),
        "total": receipt.get("total") if receipt.get("total") is not None else sum(
            (Decimal(str(item["price"])) for item in receipt["items"]), Decimal("0")
        ),
        "items": [{
            "raw_name": item["name"], "full_name": item["name"], "category": item["category"],
            "quantity": "1", "unit_price": item["price"], "total_price": item["price"],
        } for item in receipt["items"]],
    })
    payload = parsed.model_dump(mode="json")
    for line, original in zip(payload["items"], receipt["items"]):
        carbon = Decimal(str(original["carbon_kg_co2e"]))
        if not carbon.is_finite() or carbon < 0:
            raise ValueError("Carbon estimates must be finite and nonnegative.")
        line["carbon_kg_co2e"] = str(carbon)
    data = rpc("ripple_save_receipt", {
        "p_receipt": payload, "p_user_id": str(_uuid(user_id)), "p_fallback_date": date.today().isoformat(),
    })
    return _decode(_receipt, data)


def get_receipt(user_id: str, rid: str) -> dict | None:
    rows = _rows(rpc("ripple_receipts", {
        "p_user_id": str(_uuid(user_id)), "p_receipt_id": str(_uuid(rid)),
    }), _receipt)
    if len(rows) > 1:
        raise DatabaseError("Supabase returned an invalid receipt lookup response.")
    return rows[0] if rows else None


def list_receipts(user_id: str) -> list[dict]:
    return _rows(rpc("ripple_receipts", {"p_user_id": str(_uuid(user_id))}), _receipt)


def save_link(user_id: str, customer_id: str, account_id: str) -> None:
    _confirmed(rpc("ripple_save_link", {
        "p_user_id": str(_uuid(user_id)), "p_customer_id": customer_id, "p_account_id": account_id,
    }))


def get_link(user_id: str) -> dict | None:
    data = rpc("ripple_get_link", {"p_user_id": str(_uuid(user_id))})
    if data is None:
        return None
    def convert(value):
        if not all(isinstance(value[k], str) and value[k] for k in ("customer_id", "account_id")):
            raise ValueError("Invalid bank link")
        return {"customer_id": value["customer_id"], "account_id": value["account_id"]}
    return _decode(convert, data)


def _json_value(value: Any):
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    raise TypeError("Unsupported transaction JSON value")


def upsert_transactions(user_id: str, rows: list[dict]) -> int:
    payload = [{
        "id": str(row["id"]), "source": row["source"], "type": row["type"],
        "amount": str(row["amount"]), "date": str(row["date"]),
        "description": row["description"], "category": row["category"],
        "raw": json.loads(json.dumps(row.get("raw", {}), default=_json_value)),
    } for row in rows if row.get("id")]
    result = rpc("ripple_upsert_transactions", {"p_user_id": str(_uuid(user_id)), "p_rows": payload})
    def count(value):
        number = value["count"]
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise ValueError("Invalid import count")
        return number
    return _decode(count, result)


def transactions(user_id: str) -> list[dict]:
    def convert(row):
        return {
            "id": row["id"], "type": row["type"], "date": date.fromisoformat(row["date"]),
            "amount": _decimal(row["amount"]), "description": row["description"],
            "category": row["category"], "source": row["source"],
        }
    return _rows(rpc("ripple_transactions", {"p_user_id": str(_uuid(user_id))}), convert)


def ledger_entries(user_id: str) -> list[dict]:
    # Preserve main's bank-history calculation, including its expense types.
    return [{"date": row["date"], "amount": row["amount"], "source": row["source"], "type": row["type"]}
            for row in transactions(user_id) if row["type"] in {"purchase", "withdrawal", "expense"}]


def _shopping_item(row: dict) -> dict:
    result = {key: row[key] for key in ("name", "brand", "category", "allow_lower_quality")}
    result.update(id=str(_uuid(row["id"])), user_id=str(_uuid(row["user_id"])), price=float(_decimal(row["price"])))
    ShoppingListItemCreate.model_validate(result)
    return result


def add_shopping_item(user_id: str, item: dict) -> dict:
    parsed = ShoppingListItemCreate.model_validate(item)
    payload = parsed.model_dump()
    payload["price"] = str(parsed.price)
    result = _decode(_shopping_item, rpc("ripple_add_shopping_item", {
        "p_user_id": str(_uuid(user_id)), "p_item": payload,
    }))
    result.pop("user_id")
    return result


def list_shopping_items(user_id: str) -> list[dict]:
    return _rows(rpc("ripple_shopping_items", {"p_user_id": str(_uuid(user_id))}), _shopping_item)


def delete_shopping_item(user_id: str, iid: str) -> bool:
    result = rpc("ripple_delete_shopping_item", {"p_user_id": str(_uuid(user_id)), "p_item_id": str(_uuid(iid))})
    def convert(value):
        if not isinstance(value["deleted"], bool):
            raise ValueError("Invalid deletion response")
        return value["deleted"]
    return _decode(convert, result)
