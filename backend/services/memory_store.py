"""Process-local storage for the no-database demo backend."""

from datetime import date, datetime, timezone
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

_lock = RLock()
_receipts: dict[UUID, dict[str, Any]] = {}
_items: list[dict[str, Any]] = []
_shopping_list: dict[UUID, dict[str, Any]] = {}
_linked_nessie_account: dict[str, str] | None = None
_bank_transactions: list[dict[str, Any]] = []


def save_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt_id = uuid4()
    now = datetime.now(timezone.utc)
    row = {
        "id": receipt_id,
        "store": receipt.get("store"),
        "date": receipt.get("date"),
        "total": receipt.get("total"),
        "created_at": now,
        "items": [],
    }
    saved_items = []
    for line in receipt["items"]:
        item = {
            "id": uuid4(),
            "receipt_id": receipt_id,
            "name": line["name"],
            "price": line["price"],
            "category": line["category"],
            "carbon_kg_co2e": line["carbon_kg_co2e"],
        }
        saved_items.append(item)
        row["items"].append(item)
    with _lock:
        _receipts[receipt_id] = row
        _items.extend(saved_items)
    return row


def list_receipts() -> list[dict[str, Any]]:
    with _lock:
        return sorted(_receipts.values(), key=lambda row: (row["date"] or date.min, row["created_at"]), reverse=True)


def get_receipt(receipt_id: UUID) -> dict[str, Any] | None:
    with _lock:
        return _receipts.get(receipt_id)


def ledger_entries() -> list[dict[str, Any]]:
    with _lock:
        receipt_entries = [
            {"date": row["date"] or row["created_at"].date(), "amount": item["price"], "source": "receipt"}
            for row in _receipts.values()
            for item in row["items"]
        ]
        return receipt_entries + [dict(entry) for entry in _bank_transactions]


def add_shopping_item(item: dict[str, Any]) -> dict[str, Any]:
    row = {"id": uuid4(), **item}
    with _lock:
        _shopping_list[row["id"]] = row
    return row


def list_shopping_items() -> list[dict[str, Any]]:
    with _lock:
        return list(_shopping_list.values())


def delete_shopping_item(item_id: UUID) -> bool:
    with _lock:
        return _shopping_list.pop(item_id, None) is not None


def set_linked_nessie_account(customer_id: str, account_id: str) -> None:
    global _linked_nessie_account
    with _lock:
        _linked_nessie_account = {"customer_id": customer_id, "account_id": account_id}


def get_linked_nessie_account() -> dict[str, str] | None:
    with _lock:
        return dict(_linked_nessie_account) if _linked_nessie_account else None


def replace_bank_transactions(transactions: list[dict[str, Any]]) -> None:
    with _lock:
        _bank_transactions[:] = transactions
