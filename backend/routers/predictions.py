from fastapi import APIRouter

from backend.models import PredictionRequest
from backend.services.gemini_service import explain_future_savings


router = APIRouter(prefix="/api/predictions", tags=["predictions"])


def future_value_of_monthly(monthly: float, years: int, annual_return: float) -> float:
    """Value after `years` of putting `monthly` aside at the end of every month, growing at `annual_return` a year."""
    months = years * 12
    if annual_return == 0:
        return monthly * months
    # The monthly rate that compounds to exactly annual_return over twelve months.
    rate = (1 + annual_return) ** (1 / 12) - 1
    return monthly * ((1 + rate) ** months - 1) / rate


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
        monthly_spend = request.amount * request.times_per_month
        monthly_alternative_spend = alternative_amount * request.times_per_month
        monthly_savings = max(0.0, monthly_spend - monthly_alternative_spend)
        result["recurring"] = {
            "times_per_month": request.times_per_month,
            "monthly_savings": round(monthly_savings, 2),
            "annual_spend": round(monthly_spend * 12, 2),
            "annual_alternative_spend": round(monthly_alternative_spend * 12, 2),
            # Set aside over the whole period, before any growth.
            "total_saved": round(monthly_savings * 12 * request.years, 2),
            "future_value_if_spent": 0.0,
            "future_value_if_saved": round(future_value_of_monthly(monthly_spend, request.years, request.annual_return), 2),
            "future_savings": round(future_value_of_monthly(monthly_savings, request.years, request.annual_return), 2),
        }
    explanation, from_gemini = explain_future_savings(
        result.get("recurring", {}).get("future_savings", result["future_savings"]),
        request.years,
        request.annual_return,
        recurring=request.times_per_month is not None,
        alternative=request.alternative_amount is not None,
    )
    result["explanation"] = explanation
    result["explanation_source"] = "gemini" if from_gemini else "fallback"
    return result
