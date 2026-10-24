from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.routers.auth import current_user
from backend.services.sqlite_store import ledger_entries, transactions


router = APIRouter(prefix="/api/spending", tags=["spending"])


@router.get("/history")
def spending_history(days: int = Query(default=90, ge=1, le=3660), user=Depends(current_user)) -> dict[str, Any]:
    start = date.today() - timedelta(days=days - 1)
    daily: dict[date, Decimal] = defaultdict(Decimal)
    weekly: dict[date, Decimal] = defaultdict(Decimal)
    monthly: dict[str, Decimal] = defaultdict(Decimal)
    total = Decimal("0")
    for entry in ledger_entries(user["id"]):
        entry_date = entry["date"]
        if entry_date < start:
            continue
        amount = Decimal(str(entry["amount"]))
        total += amount
        daily[entry_date] += amount
        week_start = entry_date - timedelta(days=entry_date.weekday())
        weekly[week_start] += amount
        monthly[entry_date.strftime("%Y-%m")] += amount
    income=sum((Decimal(str(t["amount"])) for t in transactions(user["id"]) if t["type"]=="income" and t["date"]>=start),Decimal("0"))
    return {
        "currency": "USD",
        "range_days": days,
        "total": total,
        "income_total": income,
        "totals": {
            "daily": [{"date": key, "total": daily[key]} for key in sorted(daily)],
            "weekly": [{"week_start": key, "total": weekly[key]} for key in sorted(weekly)],
            "monthly": [{"month": key, "total": monthly[key]} for key in sorted(monthly)],
        },
    }
