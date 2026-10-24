from fastapi import APIRouter

from backend.models import PredictionRequest
from backend.services.gemini_service import explain_future_savings


router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.post("")
def predict(request: PredictionRequest) -> dict:
    factor = (1 + request.annual_return) ** request.years
    alternative_amount = request.alternative_amount or 0.0
    difference = max(0.0, request.amount - alternative_amount)
    future_savings = difference * factor
    result = {
        "amount": request.amount,
        "alternative_amount": request.alternative_amount,
        "years": request.years,
        "annual_return": request.annual_return,
        "with_purchase_future_value": 0.0,
        "without_purchase_future_value": round(request.amount * factor, 2),
        "original_future_value": round(request.amount * factor, 2),
        "alternative_future_value": round(alternative_amount * factor, 2),
        "future_savings": round(future_savings, 2),
    }
    if request.times_per_month is not None:
        annual_spend = request.amount * request.times_per_month * 12
        annual_alternative_spend = alternative_amount * request.times_per_month * 12
        recurring_difference = max(0.0, (request.amount - alternative_amount) * request.times_per_month * 12)
        result["recurring"] = {
            "times_per_month": request.times_per_month,
            "annual_spend": round(annual_spend, 2),
            "annual_alternative_spend": round(annual_alternative_spend, 2),
            "future_value_if_spent": 0.0,
            "future_value_if_saved": round(annual_spend * factor, 2),
            "future_savings": round(recurring_difference * factor, 2),
        }
    result["explanation"] = explain_future_savings(
        result.get("recurring", {}).get("future_savings", future_savings),
        request.years,
        request.annual_return,
        recurring=request.times_per_month is not None,
        alternative=request.alternative_amount is not None,
    )
    return result
