from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from backend.models import ShoppingAlternativesResponse
from backend.services.serpapi_service import ShoppingServiceError, find_alternatives


router = APIRouter(prefix="/api/shopping", tags=["shopping"])


@router.get(
    "/alternatives",
    response_model=ShoppingAlternativesResponse,
    responses={
        502: {"description": "Shopping provider failure or invalid response"},
        503: {"description": "Missing credentials or unavailable provider"},
        504: {"description": "Shopping provider timeout"},
    },
)
def get_alternatives(
    query: Annotated[str, Query(min_length=1, max_length=200)],
    original_price: Annotated[float, Query(gt=0, allow_inf_nan=False)],
    brand: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> ShoppingAlternativesResponse:
    """Find cheaper potential alternatives using USD listing prices."""
    query = query.strip()
    brand = brand.strip() if brand is not None else None
    if not query or (brand is not None and not brand):
        raise HTTPException(status_code=422, detail="Query and brand must not be blank.")
    try:
        alternatives = find_alternatives(query, original_price, brand)
    except ValueError:
        raise HTTPException(status_code=422, detail="Query must contain a product name.") from None
    except ShoppingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
    return ShoppingAlternativesResponse(
        query=query, original_price=original_price, alternatives=alternatives
    )
