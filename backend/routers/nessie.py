from typing import Any
from fastapi import APIRouter, HTTPException

from backend.models import NessieLinkRequest
from backend.services.memory_store import (
    get_linked_nessie_account,
    replace_bank_transactions,
    set_linked_nessie_account,
)
from backend.services.nessie_service import (
    NessieServiceError,
    accounts,
    customers,
    normalize_purchase,
    purchases,
)


router = APIRouter(prefix="/api/nessie", tags=["banking"])


def _provider_call(call, *args):
    try:
        return call(*args)
    except NessieServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None


@router.get("/customers")
def list_customers() -> list[dict[str, Any]]:
    return _provider_call(customers)


@router.get("/customers/{customer_id}/accounts")
def list_accounts(customer_id: str) -> list[dict[str, Any]]:
    return _provider_call(accounts, customer_id)


@router.post("/link")
def link_account(request: NessieLinkRequest) -> dict[str, str]:
    customer_id = request.customer_id.strip()
    account_id = request.account_id.strip()
    if not customer_id or not account_id:
        raise HTTPException(status_code=422, detail="Customer and account IDs must not be blank.")
    found = _provider_call(accounts, customer_id)
    if not any(str(account.get("_id") or account.get("id")) == account_id for account in found):
        raise HTTPException(status_code=404, detail="That account was not found for the selected customer.")
    set_linked_nessie_account(customer_id, account_id)
    return {"customer_id": customer_id, "account_id": account_id, "status": "linked"}


@router.get("/transactions")
def get_transactions() -> dict[str, Any]:
    linked = get_linked_nessie_account()
    if not linked:
        raise HTTPException(status_code=409, detail="Link a Nessie account with POST /api/nessie/link first.")
    raw_purchases = _provider_call(purchases, linked["account_id"])
    transactions = [
        normalized
        for purchase in raw_purchases
        if isinstance(purchase, dict)
        if (normalized := normalize_purchase(purchase)) is not None
    ]
    replace_bank_transactions(transactions)
    return {"account_id": linked["account_id"], "transactions": transactions}
