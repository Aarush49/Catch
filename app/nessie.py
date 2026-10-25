import os
from datetime import date
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://api.nessieisreal.com"


class NessieError(Exception):
    pass


class NessieClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("NESSIE_API_KEY", "")
        if not self.api_key:
            raise NessieError("NESSIE_API_KEY is not configured")
        self.client = httpx.Client(base_url=BASE_URL, timeout=20)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            response = self.client.request(method, path, params={"key": self.api_key}, json=body)
            response.raise_for_status()
            if not response.content:
                return {}
            payload = response.json()
            return payload.get("objectCreated", payload) if isinstance(payload, dict) else payload
        except (httpx.HTTPError, ValueError) as exc:
            details = getattr(getattr(exc, "response", None), "text", "")
            raise NessieError(f"Nessie request failed: {details or str(exc)}") from exc

    def get_customers(self) -> list[dict[str, Any]]:
        return self._request("GET", "/customers")

    def create_customer(self, customer: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/customers", customer)

    def get_accounts(self, customer_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/customers/{customer_id}/accounts")

    def create_account(self, customer_id: str, account: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/customers/{customer_id}/accounts", account)

    def get_purchases(self, account_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/accounts/{account_id}/purchases")

    def create_purchase(self, account_id: str, merchant_id: str, amount: float, description: str, purchase_date: date) -> dict[str, Any]:
        return self._request("POST", f"/accounts/{account_id}/purchases", {
            "merchant_id": merchant_id, "amount": amount, "description": description,
            "purchase_date": purchase_date.isoformat(), "medium": "balance",
        })

    def get_merchants(self) -> list[dict[str, Any]]:
        return self._request("GET", "/merchants")
