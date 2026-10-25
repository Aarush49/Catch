import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from backend.models import NessieLinkRequest, SavingsMoveRequest
from backend.services import supabase_store
from backend.services.supabase_jwt import current_user
from backend.services.nessie_service import (
    NessieServiceError,
    account,
    accounts,
    bills,
    create_account,
    create_bill,
    create_customer,
    create_deposit,
    create_merchant,
    create_purchase,
    create_transfer,
    customers,
    merchant_category,
    merchants,
    normalize_bill,
    normalize_purchase,
    purchases,
    deposits,
    withdrawals,
    transfers,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nessie", tags=["banking"])

DEMO_CHECKING = "CATch demo checking"
SAVINGS_ACCOUNT = "CATch savings"
DEMO_MERCHANTS = {
    "H-E-B": "Groceries", "Trader Joe's": "Groceries", "Target": "Household", "Shell": "Gas",
    "Chipotle": "Dining", "Starbucks": "Dining", "Walgreens": "Health",
}
# (merchant, whole dollars, days before today)
DEMO_PURCHASES = [
    ("H-E-B", 64, 2), ("Starbucks", 6, 3), ("Shell", 38, 4), ("Chipotle", 13, 5), ("Target", 42, 7),
    ("Trader Joe's", 51, 9), ("Walgreens", 18, 10), ("Starbucks", 7, 11), ("H-E-B", 72, 13), ("Chipotle", 12, 15),
    ("Shell", 41, 17), ("Target", 27, 19), ("Trader Joe's", 46, 21), ("Starbucks", 6, 23), ("Walgreens", 15, 26),
]
DEMO_PAYCHECK = (1850, 14, "Payroll paycheck")
# (payee, nickname, monthly amount, day of month)
DEMO_BILLS = [
    ("Rent", "Rent", 950.00, 1), ("T-Mobile", "Phone", 45.00, 12), ("Austin Energy", "Electric", 68.40, 15),
    ("Spotify", "Music", 11.99, 18), ("Netflix", "Streaming", 15.49, 22), ("Gold's Gym", "Gym", 34.99, 28),
]


def _provider_call(call, *args):
    try:
        return call(*args)
    except NessieServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None


def _savings_account_id(customer_id: str) -> str | None:
    for found in accounts(customer_id):
        if found.get("type") == "Savings" and found.get("nickname") == SAVINGS_ACCOUNT and found.get("_id"):
            return str(found["_id"])
    return None


def _fetch_bank_rows(linked: dict[str, str]) -> list[dict[str, Any]]:
    account_id = linked["account_id"]
    rows = []
    for kind, fetch in (("purchase", purchases), ("deposit", deposits), ("withdrawal", withdrawals), ("transfer", transfers)):
        for raw in fetch(account_id):
            if isinstance(raw, dict) and (normalized := normalize_purchase(raw, kind)) is not None:
                if kind == "purchase":
                    normalized["category"] = merchant_category(raw.get("merchant_id"))
                rows.append(normalized)
    rows += [bill for raw in bills(account_id) if isinstance(raw, dict) and (bill := normalize_bill(raw)) is not None]
    # Money moved into savings is recorded as deposits on the savings account; they are not income.
    savings_id = _savings_account_id(linked["customer_id"])
    for raw in deposits(savings_id) if savings_id else []:
        if isinstance(raw, dict) and (normalized := normalize_purchase(raw, "deposit")) is not None:
            rows.append({**normalized, "type": "savings", "category": "savings"})
    return rows


def _import_transactions(user_id: str, linked: dict[str, str]) -> dict[str, Any]:
    rows = _provider_call(_fetch_bank_rows, linked)
    count = supabase_store.upsert_transactions(user_id, rows)
    supabase_store.prune_transactions(user_id, "bill", [str(row["id"]) for row in rows if row["type"] == "bill" and row.get("id")])
    return {"account_id": linked["account_id"], "count": count, "transactions": supabase_store.transactions(user_id)}


def _demo_merchant_ids() -> dict[str, str]:
    existing = {}
    for merchant in merchants():
        name, merchant_id = merchant.get("name"), merchant.get("_id")
        if name in DEMO_MERCHANTS and merchant_id and name not in existing:
            existing[name] = str(merchant_id)
    for name, category in DEMO_MERCHANTS.items():
        if name not in existing:
            existing[name] = str(create_merchant(name, category)["_id"])
    return existing


def _add_demo_bills(account_id: str) -> None:
    today = date.today()
    for payee, nickname, amount, day in DEMO_BILLS:
        create_bill(account_id, payee, nickname, amount, day, today)


def _create_demo_bank() -> tuple[str, str]:
    merchant_ids = _demo_merchant_ids()
    customer_id = str(create_customer("CATch", "Demo")["_id"])
    account_id = str(create_account(customer_id, DEMO_CHECKING, 2500)["_id"])
    create_account(customer_id, SAVINGS_ACCOUNT, 0, "Savings")
    today = date.today()
    for merchant, amount, days_ago in DEMO_PURCHASES:
        create_purchase(account_id, merchant_ids[merchant], amount, today - timedelta(days=days_ago), merchant)
    amount, days_ago, description = DEMO_PAYCHECK
    create_deposit(account_id, amount, today - timedelta(days=days_ago), description)
    _add_demo_bills(account_id)
    return customer_id, account_id


def _update_demo_bank(account_id: str) -> None:
    """Give a demo account created before bills existed its bills; accounts linked by hand are left alone."""
    if account(account_id).get("nickname") == DEMO_CHECKING and not bills(account_id):
        _add_demo_bills(account_id)


@router.get("/customers")
def list_customers(user=Depends(current_user)) -> list[dict[str, Any]]:
    return _provider_call(customers)


@router.get("/customers/{customer_id}/accounts")
def list_accounts(customer_id: str, user=Depends(current_user)) -> list[dict[str, Any]]:
    return _provider_call(accounts, customer_id)


@router.post("/link")
def link_account(request: NessieLinkRequest, user=Depends(current_user)) -> dict[str, str]:
    customer_id = request.customer_id.strip()
    account_id = request.account_id.strip()
    if not customer_id or not account_id:
        raise HTTPException(status_code=422, detail="Customer and account IDs must not be blank.")
    found = _provider_call(accounts, customer_id)
    if not any(str(account.get("_id") or account.get("id")) == account_id for account in found):
        raise HTTPException(status_code=404, detail="That account was not found for the selected customer.")
    supabase_store.save_link(user["id"], customer_id, account_id)
    return {"customer_id": customer_id, "account_id": account_id, "status": "linked"}


@router.post("/demo-bank")
def connect_demo_bank(user=Depends(current_user)) -> dict[str, Any]:
    """Create, seed and link a sandbox checking account; if one is already linked, re-import it instead."""
    linked = supabase_store.get_link(user["id"])
    created = linked is None
    if created:
        # The link is saved only after seeding succeeds, so a failed attempt can simply be retried.
        customer_id, account_id = _provider_call(_create_demo_bank)
        supabase_store.save_link(user["id"], customer_id, account_id)
        linked = {"customer_id": customer_id, "account_id": account_id}
    else:
        _provider_call(_update_demo_bank, linked["account_id"])
    return {**_import_transactions(user["id"], linked), "created": created}


@router.get("/transactions")
def get_transactions(user=Depends(current_user)) -> dict[str, Any]:
    linked = supabase_store.get_link(user["id"])
    if not linked:
        raise HTTPException(status_code=409, detail="Link a Nessie account with POST /api/nessie/link first.")
    return _import_transactions(user["id"], linked)


@router.post("/savings")
def move_to_savings(request: SavingsMoveRequest, user=Depends(current_user)) -> dict[str, Any]:
    """Move money from the linked checking account into the user's CATch savings account (created on first use)."""
    linked = supabase_store.get_link(user["id"])
    if not linked:
        raise HTTPException(status_code=409, detail="Connect a demo bank in your profile to move savings.")
    # Nessie keeps whole dollars only, so the amount is rounded to the nearest dollar.
    dollars = int(Decimal(str(request.amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if dollars >= 1:
        savings_id = _provider_call(_savings_account_id, linked["customer_id"])
        if savings_id is None:
            savings_id = str(_provider_call(create_account, linked["customer_id"], SAVINGS_ACCOUNT, 0, "Savings")["_id"])
        description = f"To savings: {request.description.strip()}"[:200]
        today = date.today()
        _provider_call(create_deposit, savings_id, dollars, today, description)
        try:
            create_transfer(linked["account_id"], dollars, today, description)
        except NessieServiceError as exc:
            # The savings deposit is what the app shows; the checking-side record is best effort.
            logger.warning("Savings deposit made but the checking transfer failed: %s", exc)
    else:
        dollars = 0
    imported = _import_transactions(user["id"], linked)
    savings_total = sum((row["amount"] for row in imported["transactions"] if row["type"] == "savings"), Decimal("0"))
    return {"moved": dollars, "savings_total": savings_total}
