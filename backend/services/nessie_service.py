"""Minimal Capital One Nessie sandbox client using HTTPS."""

import os
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx


NESSIE_BASE_URL = "https://api.nessieisreal.com"


class NessieServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _request(method: str, path: str) -> Any:
    api_key = os.getenv("NESSIE_API_KEY", "").strip()
    if not api_key:
        raise NessieServiceError("Bank sandbox is not configured (NESSIE_API_KEY).", 503)
    try:
        response = httpx.request(
            method,
            f"{NESSIE_BASE_URL}{path}",
            params={"key": api_key},  # Nessie requires this parameter; HTTPS protects it in transit.
            timeout=15,
        )
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
    result = _request("GET", f"/accounts/{quote(account_id, safe='')}/purchases")
    if not isinstance(result, list):
        raise NessieServiceError("Bank sandbox returned an invalid transaction list.")
    return result


def normalize_purchase(purchase: dict[str, Any]) -> dict[str, Any] | None:
    try:
        amount = Decimal(str(purchase.get("amount")))
        if not amount.is_finite() or amount <= 0:
            return None
        purchased_on = date.fromisoformat(str(purchase.get("purchase_date") or purchase.get("date"))[:10])
    except (InvalidOperation, TypeError, ValueError):
        return None
    txn_id = purchase.get("_id") or purchase.get("id")
    return {
        "id": str(txn_id) if txn_id else None,
        "date": purchased_on,
        "amount": amount,
        "description": str(purchase.get("description") or "Purchase"),
        "merchant_id": purchase.get("merchant_id"),
        "source": "nessie",
    }
