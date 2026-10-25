"""Minimal Capital One Nessie sandbox client using HTTPS."""

import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx


NESSIE_BASE_URL = "https://api.nessieisreal.com"


class NessieServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _request(method: str, path: str, body: dict[str, Any] | None = None, *, empty_if_missing: bool = False) -> Any:
    api_key = os.getenv("NESSIE_API_KEY", "").strip()
    if not api_key:
        raise NessieServiceError("Bank sandbox is not configured (NESSIE_API_KEY).", 503)
    try:
        response = httpx.request(
            method,
            f"{NESSIE_BASE_URL}{path}",
            params={"key": api_key},  # Nessie requires this parameter; HTTPS protects it in transit.
            json=body,
            timeout=15,
        )
        # Some Nessie list endpoints answer 404 instead of [] when there is nothing to list.
        if empty_if_missing and response.status_code == 404:
            return []
        response.raise_for_status()
        payload = response.json() if response.content else {}
    except httpx.TimeoutException:
        raise NessieServiceError("Bank sandbox request timed out.", 504) from None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403, 429}:
            raise NessieServiceError("Bank sandbox credentials or quota are unavailable.", 503) from None
        raise NessieServiceError("Bank sandbox request failed.", 502) from None
    except (httpx.HTTPError, ValueError):
        # Do not include request URLs or provider response bodies: both may contain secrets.
        raise NessieServiceError("Bank sandbox request failed.", 502) from None
    if isinstance(payload, dict) and "objectCreated" in payload:
        return payload["objectCreated"]
    return payload


def customers() -> list[dict[str, Any]]:
    result = _request("GET", "/customers")
    if not isinstance(result, list):
        raise NessieServiceError("Bank sandbox returned an invalid customer list.")
    return result


def accounts(customer_id: str) -> list[dict[str, Any]]:
    result = _request("GET", f"/customers/{quote(customer_id, safe='')}/accounts")
    if not isinstance(result, list):
        raise NessieServiceError("Bank sandbox returned an invalid account list.")
    return result


def purchases(account_id: str) -> list[dict[str, Any]]:
    return _transactions(account_id, "purchases")


def _transactions(account_id: str, kind: str, empty_if_missing: bool = False) -> list[dict[str, Any]]:
    result = _request("GET", f"/accounts/{quote(account_id, safe='')}/{kind}", empty_if_missing=empty_if_missing)
    if not isinstance(result, list):
        raise NessieServiceError("Bank sandbox returned an invalid transaction list.")
    return result


def deposits(account_id: str) -> list[dict[str, Any]]:
    return _transactions(account_id, "deposits")


def withdrawals(account_id: str) -> list[dict[str, Any]]:
    return _transactions(account_id, "withdrawals")


def transfers(account_id: str) -> list[dict[str, Any]]:
    # Nessie answers 404 "No transfers found for this account" for an account without transfers.
    return _transactions(account_id, "transfers", empty_if_missing=True)


def bills(account_id: str) -> list[dict[str, Any]]:
    return _transactions(account_id, "bills")


def account(account_id: str) -> dict[str, Any]:
    result = _request("GET", f"/accounts/{quote(account_id, safe='')}")
    if not isinstance(result, dict):
        raise NessieServiceError("Bank sandbox returned an invalid account.")
    return result


def merchants() -> list[dict[str, Any]]:
    result = _request("GET", "/merchants")
    if not isinstance(result, list):
        raise NessieServiceError("Bank sandbox returned an invalid merchant list.")
    return result


# Values match backend.models.ExpenseCategory; checked in order, so groceries wins over generic "food".
_CATEGORY_KEYWORDS = (
    ("groceries", ("grocer", "supermarket", "food market")),
    ("restaurant", ("dining", "restaurant", "coffee", "cafe", "fast food")),
    ("health", ("health", "pharmacy", "drug", "medical")),
    ("transportation", ("gas", "fuel", "transport", "auto", "parking", "transit")),
    ("household", ("household", "home", "department", "general merchandise", "hardware", "retail")),
)
_merchant_categories: dict[str, str] = {}


def spending_category(merchant_category: Any) -> str:
    """Map a Nessie merchant category (a string, or a list of strings) to an ExpenseCategory value."""
    parts = merchant_category if isinstance(merchant_category, list) else [merchant_category]
    text = " ".join(part for part in parts if isinstance(part, str)).casefold()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return "other"


def merchant_category(merchant_id: Any) -> str:
    """The spending category of a purchase's merchant; "other" if it cannot be looked up right now."""
    if not isinstance(merchant_id, str) or not merchant_id:
        return "other"
    if merchant_id not in _merchant_categories:
        try:
            result = _request("GET", f"/merchants/{quote(merchant_id, safe='')}")
        except NessieServiceError:
            return "other"  # not cached, so the next import retries
        _merchant_categories[merchant_id] = spending_category(result.get("category") if isinstance(result, dict) else None)
    return _merchant_categories[merchant_id]


def _created(result: Any, what: str) -> dict[str, Any]:
    if not isinstance(result, dict) or not result.get("_id"):
        raise NessieServiceError(f"Bank sandbox did not confirm the new {what}.")
    return result


_DEMO_ADDRESS = {"street_number": "110", "street_name": "Inner Campus Dr", "city": "Austin", "state": "TX", "zip": "78712"}


def create_merchant(name: str, category: str) -> dict[str, Any]:
    return _created(_request("POST", "/merchants", {
        "name": name, "category": category, "address": _DEMO_ADDRESS, "geocode": {"lat": 30.2849, "lng": -97.7341},
    }), "merchant")


def create_customer(first_name: str, last_name: str) -> dict[str, Any]:
    return _created(_request("POST", "/customers", {
        "first_name": first_name, "last_name": last_name, "address": _DEMO_ADDRESS,
    }), "customer")


def create_account(customer_id: str, nickname: str, balance: int, account_type: str = "Checking") -> dict[str, Any]:
    return _created(_request("POST", f"/customers/{quote(customer_id, safe='')}/accounts", {
        "type": account_type, "nickname": nickname, "rewards": 0, "balance": balance,
    }), "account")


def next_due_date(recurring_day: int, today: date) -> date:
    """The next date (today or later) falling on recurring_day; days are limited to 1-28 so every month has one."""
    if not 1 <= recurring_day <= 28:
        raise ValueError("recurring_day must be between 1 and 28.")
    if recurring_day >= today.day:
        return today.replace(day=recurring_day)
    return (today.replace(day=1) + timedelta(days=32)).replace(day=recurring_day)


# Nessie lists an account's bills only if every bill has a nickname, payment date and recurring day.
def create_bill(account_id: str, payee: str, nickname: str, amount: float, recurring_day: int, today: date) -> dict[str, Any]:
    return _created(_request("POST", f"/accounts/{quote(account_id, safe='')}/bills", {
        "status": "recurring", "payee": payee, "nickname": nickname,
        "payment_date": next_due_date(recurring_day, today).isoformat(), "recurring_date": recurring_day,
        "payment_amount": amount,
    }), "bill")


# This Nessie server's transfers have no payee field; they only record money leaving the account.
def create_transfer(account_id: str, amount: int, transaction_date: date, description: str) -> dict[str, Any]:
    return _created(_request("POST", f"/accounts/{quote(account_id, safe='')}/transfers", {
        "transaction_date": transaction_date.isoformat(), "status": "completed",
        "amount": amount, "description": description,
    }), "transfer")


# Nessie stores amounts as whole dollars (it truncates cents), so amounts are ints.
# Without a status, Nessie accepts a purchase but then fails to list the account's purchases.
def create_purchase(account_id: str, merchant_id: str, amount: int, purchase_date: date, description: str) -> dict[str, Any]:
    return _created(_request("POST", f"/accounts/{quote(account_id, safe='')}/purchases", {
        "merchant_id": merchant_id, "medium": "balance", "purchase_date": purchase_date.isoformat(),
        "amount": amount, "status": "completed", "description": description,
    }), "purchase")


def create_deposit(account_id: str, amount: int, transaction_date: date, description: str) -> dict[str, Any]:
    return _created(_request("POST", f"/accounts/{quote(account_id, safe='')}/deposits", {
        "medium": "balance", "transaction_date": transaction_date.isoformat(),
        "amount": amount, "status": "completed", "description": description,
    }), "deposit")


def normalize_purchase(purchase: dict[str, Any], kind: str = "purchase") -> dict[str, Any] | None:
    try:
        amount = Decimal(str(purchase.get("amount")))
        if not amount.is_finite() or amount == 0:
            return None
        purchased_on = date.fromisoformat(str(purchase.get("purchase_date") or purchase.get("transaction_date") or purchase.get("date"))[:10])
    except (InvalidOperation, TypeError, ValueError):
        return None
    txn_id = purchase.get("_id") or purchase.get("id")
    description=str(purchase.get("description") or purchase.get("medium") or kind.title())
    normalized_kind=kind
    category=kind
    if kind == "deposit" and any(word in description.lower() for word in ("salary","payroll","paycheck","pay check","wage")):
        normalized_kind="income"
        category="salary"
    return {
        "id": str(txn_id) if txn_id else None,
        "date": purchased_on,
        "amount": amount,
        "description": description,
        "merchant_id": purchase.get("merchant_id"),
        "source": "nessie",
        "type": normalized_kind,
        "category": category,
        "raw": purchase,
    }


def normalize_bill(bill: dict[str, Any]) -> dict[str, Any] | None:
    """An upcoming bill as a "bill" row dated on its next payment date; paid or cancelled bills are skipped."""
    if str(bill.get("status", "")).lower() not in {"recurring", "pending"}:
        return None
    try:
        amount = Decimal(str(bill.get("payment_amount")))
        if not amount.is_finite() or amount <= 0:
            return None
        due = date.fromisoformat(str(bill.get("upcoming_payment_date") or bill.get("payment_date"))[:10])
    except (InvalidOperation, TypeError, ValueError):
        return None
    bill_id = bill.get("_id") or bill.get("id")
    return {
        "id": str(bill_id) if bill_id else None,
        "date": due,
        "amount": amount,
        "description": str(bill.get("payee") or bill.get("nickname") or "Bill"),
        "merchant_id": None,
        "source": "nessie",
        "type": "bill",
        "category": "bill",
        "raw": bill,
    }
