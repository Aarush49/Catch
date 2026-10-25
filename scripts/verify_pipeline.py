"""End-to-end check of the live data pipeline. Run: python -m scripts.verify_pipeline

Creates two temporary, pre-confirmed Supabase Auth users, exercises receipt
saving/editing/row-level security and the backend's authenticated routes as
those users, then deletes both users (which cascades to every row they own).
Set SUPABASE_PUBLISHABLE_KEY to sign in exactly as the app does; otherwise the
backend secret key is used as the API key with each user's own session token.
"""

import os
import secrets
import sys
from decimal import Decimal

import httpx
from fastapi.testclient import TestClient

from app.database import DatabaseError, _configuration, check_connection
from app.main import app

TIMEOUT = 20


class Check:
    def __init__(self):
        self.failures = 0

    def __call__(self, label: str, ok: bool, detail: str = ""):
        print(f"{'PASS' if ok else 'FAIL'}  {label}{f'  ({detail})' if detail and not ok else ''}")
        self.failures += not ok


def main() -> int:
    check = Check()
    try:
        check_connection()
        url, secret = _configuration()
    except DatabaseError as exc:
        print(f"FAIL  schema check: {exc}")
        return 1
    check("schema version and tables", True)
    api_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip() or secret
    admin = httpx.Client(base_url=url, headers={"apikey": secret}, timeout=TIMEOUT)
    users: list[str] = []

    def create_user() -> tuple[str, str]:
        email = f"pipeline-check-{secrets.token_hex(6)}@example.com"
        password = secrets.token_urlsafe(18)
        response = admin.post("/auth/v1/admin/users", json={"email": email, "password": password, "email_confirm": True})
        response.raise_for_status()
        users.append(response.json()["id"])
        token = httpx.post(f"{url}/auth/v1/token", params={"grant_type": "password"}, headers={"apikey": api_key},
                           json={"email": email, "password": password}, timeout=TIMEOUT)
        token.raise_for_status()
        return response.json()["id"], token.json()["access_token"]

    def rest(token: str) -> httpx.Client:
        return httpx.Client(base_url=f"{url}/rest/v1", timeout=TIMEOUT,
                            headers={"apikey": api_key, "Authorization": f"Bearer {token}"})

    try:
        user_a, token_a = create_user()
        user_b, token_b = create_user()
        a, b = rest(token_a), rest(token_b)
        profiles = a.get("/profiles", params={"select": "id"}).json()
        check("sign-up trigger creates a profile", profiles == [{"id": user_a}], str(profiles))

        columns = "id,user_id,merchant,purchased_at,subtotal,tax,total,receipt_items(position,name,quantity,price,category,carbon_kg_co2e)"
        receipt = {"id": None, "merchant": " H-E-B ", "purchased_at": "2026-10-24", "tax": 0.35, "items": [
            {"name": "Oat milk", "quantity": 2, "price": 4.19, "category": "Groceries", "carbon_kg_co2e": 1.01},
            {"name": "Dish soap", "quantity": 1, "price": 4.49, "category": "Household", "carbon_kg_co2e": 0.45},
        ]}
        saved = a.post("/rpc/save_receipt", json={"p_receipt": receipt})
        check("user A saves a receipt through save_receipt", saved.status_code == 200, saved.text)
        receipt_id = saved.json()
        row = a.get("/receipts", params={"select": columns, "id": f"eq.{receipt_id}"}).json()[0]
        items = sorted(row["receipt_items"], key=lambda item: item["position"])
        check("receipt belongs to user A", row["user_id"] == user_a)
        check("merchant trimmed, date stored", row["merchant"] == "H-E-B" and row["purchased_at"] == "2026-10-24")
        check("subtotal = sum(price * quantity), total = subtotal + tax",
              Decimal(str(row["subtotal"])) == Decimal("12.87") and Decimal(str(row["total"])) == Decimal("13.22"),
              f"{row['subtotal']} / {row['total']}")
        check("items stored in order with carbon",
              [(i["name"], i["position"], Decimal(str(i["carbon_kg_co2e"]))) for i in items]
              == [("Oat milk", 0, Decimal("1.01")), ("Dish soap", 1, Decimal("0.45"))], str(items))

        edited = {**receipt, "id": receipt_id, "tax": 0, "items": [
            {"name": "Oat milk", "quantity": 1, "price": 3.19, "category": "Groceries", "carbon_kg_co2e": 0.38}]}
        check("user A edits the receipt", a.post("/rpc/save_receipt", json={"p_receipt": edited}).status_code == 200)
        row = a.get("/receipts", params={"select": columns, "id": f"eq.{receipt_id}"}).json()[0]
        check("edit replaces items and recomputes totals",
              len(row["receipt_items"]) == 1 and Decimal(str(row["total"])) == Decimal("3.19"), str(row))

        before = len(a.get("/receipts", params={"select": "id"}).json())
        bad = {**receipt, "items": [receipt["items"][0], {"name": "Broken", "quantity": 1, "price": -1, "category": "Other"}]}
        failed = a.post("/rpc/save_receipt", json={"p_receipt": bad})
        after = len(a.get("/receipts", params={"select": "id"}).json())
        check("a bad line rejects the whole receipt (nothing half-saved)",
              failed.status_code >= 400 and before == after, f"status {failed.status_code}, {before} -> {after}")

        check("user B cannot read user A's receipts",
              b.get("/receipts", params={"select": "id"}).json() == [])
        check("user B cannot read user A's items",
              b.get("/receipt_items", params={"select": "id"}).json() == [])
        hijack = b.post("/rpc/save_receipt", json={"p_receipt": {**edited, "items": []}})
        check("user B cannot overwrite user A's receipt", hijack.status_code >= 400, hijack.text)
        deleted = b.delete("/receipts", params={"id": f"eq.{receipt_id}"}, headers={"Prefer": "return=representation"})
        check("user B cannot delete user A's receipt", deleted.json() == [], deleted.text)
        forged = b.post("/receipts", json={"user_id": user_a, "merchant": "forged"})
        check("user B cannot insert rows as user A", forged.status_code >= 400, forged.text)
        bank = a.post("/transactions", json={"user_id": user_a, "source": "x", "external_id": "x",
                                             "transaction_type": "purchase", "amount": 1, "date": "2026-10-24"})
        check("users cannot write bank transactions directly", bank.status_code >= 400, bank.text)

        with TestClient(app) as api:
            empty = api.post("/receipts/scan", headers={"Authorization": f"Bearer {token_a}"},
                             files={"file": ("receipt.jpg", b"", "image/jpeg")})
            check("backend accepts a real Supabase session (scan route)", empty.status_code == 400, empty.text)
            forged_token = token_a[:-4] + ("AAAA" if not token_a.endswith("AAAA") else "BBBB")
            denied = api.post("/receipts/scan", headers={"Authorization": f"Bearer {forged_token}"},
                              files={"file": ("receipt.jpg", b"x", "image/jpeg")})
            check("backend rejects a tampered session", denied.status_code == 401, denied.text)
            headers_a, headers_b = {"Authorization": f"Bearer {token_a}"}, {"Authorization": f"Bearer {token_b}"}
            created = api.post("/api/shopping-list/items", headers=headers_a, json={"name": "Shoes", "price": 80.10})
            check("backend saves a shopping item for user A", created.status_code == 201, created.text)
            listed_a = api.get("/api/shopping-list/items", headers=headers_a).json()
            listed_b = api.get("/api/shopping-list/items", headers=headers_b).json()
            check("backend shopping list is per user", len(listed_a) == 1 and listed_b == [], f"{listed_a} / {listed_b}")
            visible = a.get("/shopping_items", params={"select": "name"}).json()
            check("app sees the backend's shopping item through RLS", visible == [{"name": "Shoes"}], str(visible))
            item_id = created.json().get("id")
            check("user B cannot delete user A's item via backend",
                  api.delete(f"/api/shopping-list/items/{item_id}", headers=headers_b).status_code == 404)
            check("user A deletes the item via backend",
                  api.delete(f"/api/shopping-list/items/{item_id}", headers=headers_a).status_code == 204)
            check("bank routes need a linked account first",
                  api.get("/api/nessie/transactions", headers=headers_a).status_code == 409)

        if api_key != secret:
            anon = httpx.get(f"{url}/rest/v1/receipts", params={"select": "id"}, headers={"apikey": api_key}, timeout=TIMEOUT)
            check("signed-out requests see no receipts", anon.status_code >= 400 or anon.json() == [], anon.text)
    except httpx.HTTPError as exc:
        check("live request", False, f"{type(exc).__name__}: {exc}"[:300])
    finally:
        for user_id in users:
            admin.delete(f"/auth/v1/admin/users/{user_id}")
        if users:
            leftovers = admin.get("/rest/v1/receipts", params={"select": "id", "user_id": f"in.({','.join(users)})"}).json()
            check("temporary users and their rows were deleted", leftovers == [], str(leftovers))
    print("All pipeline checks passed." if not check.failures else f"{check.failures} check(s) failed.")
    return 1 if check.failures else 0


if __name__ == "__main__":
    sys.exit(main())
