from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from backend.models import NessieLinkRequest
from backend.services import supabase_store
from backend.services.supabase_jwt import current_user
from backend.services.nessie_service import (
    NessieServiceError,
    accounts,
    customers,
    normalize_purchase,
    purchases,
    deposits,
    withdrawals,
    transfers,
)


router = APIRouter(prefix="/api/nessie", tags=["banking"])


def _provider_call(call, *args):
    try:
        return call(*args)
    except NessieServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None


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


@router.get("/transactions")
def get_transactions(user=Depends(current_user)) -> dict[str, Any]:
    linked = supabase_store.get_link(user["id"])
    if not linked:
        raise HTTPException(status_code=409, detail="Link a Nessie account with POST /api/nessie/link first.")
    imported=[]
    for kind, fetch in (("purchase",purchases),("deposit",deposits),("withdrawal",withdrawals),("transfer",transfers)):
        raw_rows = _provider_call(fetch, linked["account_id"])
        for raw in raw_rows:
            if isinstance(raw,dict) and (normalized:=normalize_purchase(raw,kind)) is not None:
                imported.append(normalized)
    count=supabase_store.upsert_transactions(user["id"],imported)
    return {"account_id":linked["account_id"],"count":count,"transactions":supabase_store.transactions(user["id"])}
