"""Thread-safe in-memory storage for receipts, items, and demo account IDs."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

_lock = RLock()
_receipts: dict[UUID, dict[str, Any]] = {}
_items: list[dict[str, Any]] = []
_nessie_demo_ids: tuple[str, str] | None = None


def save_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    purchased_date: date = receipt["purchase_date"] or date.today()
    now = datetime.now(timezone.utc)
    receipt_id = uuid4()
    row = {
        "id": receipt_id,
        "store_name": receipt["store_name"],
        "purchase_date": receipt["purchase_date"],
        "subtotal": receipt["subtotal"],
        "tax": receipt["tax"],
        "total": receipt["total"],
        "raw_json": receipt,
        "created_at": now,
    }
    purchased_at = datetime.combine(purchased_date, time.min, tzinfo=timezone.utc)
    saved_items = []
    for item in receipt["items"]:
        saved_items.append({
            "id": uuid4(),
            "receipt_id": receipt_id,
            "raw_name": item["raw_name"],
            "full_name": item["full_name"],
            "category": item["category"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
            "total_price": item["total_price"],
            "purchased_at": purchased_at,
            "created_at": now,
        })
    with _lock:
        _receipts[receipt_id] = row
        _items.extend(saved_items)
    return _receipt_dict(row, saved_items)


def _receipt_dict(row: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    result = {**row, "items": items}
    result["warnings"] = row["raw_json"].get("warnings", [])
    return result


def list_receipts() -> list[dict[str, Any]]:
    with _lock:
        rows = sorted(
            _receipts.values(),
            key=lambda row: (row["purchase_date"] is not None, row["purchase_date"] or date.min, row["created_at"]),
            reverse=True,
        )
        return [
            _receipt_dict(row, sorted(
                (item for item in _items if item["receipt_id"] == row["id"]),
                key=lambda item: item["created_at"],
            ))
            for row in rows
        ]


def get_receipt(receipt_id: UUID) -> dict[str, Any] | None:
    with _lock:
        row = _receipts.get(receipt_id)
        if row is None:
            return None
        items = sorted(
            (item for item in _items if item["receipt_id"] == receipt_id),
            key=lambda item: item["created_at"],
        )
        return _receipt_dict(row, items)


def list_items(category: str | None, start: date | None, end: date | None) -> list[dict[str, Any]]:
    start_at = datetime.combine(start, time.min, tzinfo=timezone.utc) if start else None
    end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc) if end else None
    with _lock:
        result = [
            item for item in _items
            if (category is None or item["category"] == category)
            and (start_at is None or item["purchased_at"] >= start_at)
            and (end_at is None or item["purchased_at"] < end_at)
        ]
        return sorted(result, key=lambda item: (item["purchased_at"], item["created_at"]), reverse=True)


def spending_summary(period: str) -> dict[str, Any]:
    cutoff = {"week": datetime.now(timezone.utc) - timedelta(days=7),
              "month": datetime.now(timezone.utc) - timedelta(days=30)}.get(period)
    with _lock:
        selected = [item for item in _items if cutoff is None or item["purchased_at"] >= cutoff]
    categories: dict[str, Decimal] = {}
    days: dict[date, Decimal] = {}
    for item in selected:
        categories[item["category"]] = categories.get(item["category"], Decimal("0")) + item["total_price"]
        day = item["purchased_at"].astimezone(timezone.utc).date()
        days[day] = days.get(day, Decimal("0")) + item["total_price"]
    return {
        "period": period,
        "by_category": [{"category": key, "total": categories[key]} for key in sorted(categories)],
        "by_day": [{"day": key, "total": days[key]} for key in sorted(days)],
    }


def get_demo_ids() -> tuple[str, str] | None:
    with _lock:
        return _nessie_demo_ids


def set_demo_ids(customer_id: str, account_id: str) -> None:
    global _nessie_demo_ids
    with _lock:
        _nessie_demo_ids = (customer_id, account_id)
