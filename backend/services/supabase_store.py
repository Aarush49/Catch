"""Service-role persistence for the backend's per-user routes.

The service-role key bypasses row level security, so every query here filters
by the verified Supabase user ID.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from uuid import UUID

from app.database import DatabaseError, execute
from backend.models import ShoppingListItemCreate


def _uuid(value: UUID | str) -> str:
    try:
        return str(value if isinstance(value, UUID) else UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A valid UUID is required.") from None


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("A finite decimal is required.")
    return result


def _rows(data, convert: Callable) -> list:
    if not isinstance(data, list):
        raise DatabaseError("Supabase returned an invalid collection response.")
    try:
        return [convert(row) for row in data]
    except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
        raise DatabaseError("Supabase returned invalid stored data.") from None


def save_link(user_id: str, customer_id: str, account_id: str) -> None:
    execute(lambda client: client.table("linked_accounts").upsert({
        "user_id": _uuid(user_id), "provider": "nessie",
        "customer_id": customer_id, "account_id": account_id,
    }, on_conflict="user_id"))


def get_link(user_id: str) -> dict | None:
    data = execute(lambda client: client.table("linked_accounts").select("customer_id,account_id")
                   .eq("user_id", _uuid(user_id)).limit(1))
    rows = _rows(data, lambda row: {"customer_id": str(row["customer_id"]), "account_id": str(row["account_id"])})
    return rows[0] if rows else None


def _json_value(value: Any):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def upsert_transactions(user_id: str, rows: list[dict]) -> int:
    owner = _uuid(user_id)
    # One upsert cannot touch the same conflict key twice, so keep the last copy.
    unique = {(row["source"], str(row["id"])): row for row in rows if row.get("id")}
    payload = [{
        "user_id": owner, "source": source, "external_id": external_id,
        "transaction_type": row["type"], "amount": str(row["amount"]), "date": str(row["date"]),
        "description": row["description"], "category": row["category"],
        "raw_json": _json_value(row.get("raw", {})),
    } for (source, external_id), row in unique.items()]
    if not payload:
        return 0
    data = execute(lambda client: client.table("transactions")
                   .upsert(payload, on_conflict="user_id,source,external_id"))
    if not isinstance(data, list):
        raise DatabaseError("Supabase did not confirm the imported transactions.")
    return len(data)


def prune_transactions(user_id: str, transaction_type: str, keep_external_ids: list[str]) -> None:
    """Delete this user's Nessie rows of one type that the latest import no longer returned."""
    def build(client):
        query = (client.table("transactions").delete().eq("user_id", _uuid(user_id))
                 .eq("source", "nessie").eq("transaction_type", transaction_type))
        return query.not_.in_("external_id", keep_external_ids) if keep_external_ids else query
    execute(build)


def transactions(user_id: str) -> list[dict]:
    data = execute(lambda client: client.table("transactions")
                   .select("external_id,transaction_type,date,amount,description,category,source")
                   .eq("user_id", _uuid(user_id)).order("date"))

    def convert(row):
        return {
            "id": row["external_id"], "type": row["transaction_type"], "date": date.fromisoformat(row["date"]),
            "amount": _decimal(row["amount"]), "description": row["description"],
            "category": row["category"], "source": row["source"],
        }
    return _rows(data, convert)


def ledger_entries(user_id: str) -> list[dict]:
    return [{"date": row["date"], "amount": row["amount"], "source": row["source"], "type": row["type"]}
            for row in transactions(user_id) if row["type"] in {"purchase", "withdrawal", "expense"}]


SHOPPING_COLUMNS = "id,name,price,brand,category,allow_lower_quality,completed"


def _shopping_item(row: dict) -> dict:
    price = _decimal(row["price"])
    return {
        "id": _uuid(row["id"]), "name": row["name"], "price": float(price) if price is not None else None,
        "brand": row["brand"], "category": row["category"],
        "allow_lower_quality": bool(row["allow_lower_quality"]), "completed": bool(row["completed"]),
    }


def add_shopping_item(user_id: str, item: dict) -> dict:
    parsed = ShoppingListItemCreate.model_validate(item)
    values = parsed.model_dump()
    values["price"] = str(parsed.price)
    data = execute(lambda client: client.table("shopping_items")
                   .insert({**values, "user_id": _uuid(user_id)}))
    rows = _rows(data, _shopping_item)
    if len(rows) != 1:
        raise DatabaseError("Supabase did not confirm the shopping list item.")
    return rows[0]


def list_shopping_items(user_id: str) -> list[dict]:
    data = execute(lambda client: client.table("shopping_items").select(SHOPPING_COLUMNS)
                   .eq("user_id", _uuid(user_id)).order("created_at"))
    return _rows(data, _shopping_item)


def delete_shopping_item(user_id: str, item_id: str) -> bool:
    data = execute(lambda client: client.table("shopping_items").delete()
                   .eq("id", _uuid(item_id)).eq("user_id", _uuid(user_id)))
    if not isinstance(data, list):
        raise DatabaseError("Supabase did not confirm the deletion.")
    return len(data) > 0
