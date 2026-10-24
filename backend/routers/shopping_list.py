import os
from uuid import UUID

from fastapi import APIRouter, HTTPException

from backend.models import (
    ShoppingListComparisonResponse,
    ShoppingListItemCreate,
)
from backend.services.memory_store import add_shopping_item, delete_shopping_item, list_shopping_items
from backend.services.serpapi_service import ShoppingServiceError, find_alternatives


router = APIRouter(prefix="/api/shopping-list", tags=["shopping list"])


@router.get("/items")
def get_shopping_items() -> list[dict]:
    return list_shopping_items()


@router.post("/items", status_code=201)
def create_shopping_item(item: ShoppingListItemCreate) -> dict:
    values = item.model_dump()
    values["name"] = values["name"].strip()
    if values["brand"] is not None:
        values["brand"] = values["brand"].strip() or None
    if not values["name"]:
        raise HTTPException(status_code=422, detail="Item name must not be blank.")
    return add_shopping_item(values)


@router.delete("/items/{item_id}", status_code=204)
def remove_shopping_item(item_id: UUID) -> None:
    if not delete_shopping_item(item_id):
        raise HTTPException(status_code=404, detail="Shopping list item not found.")


@router.post("/done", response_model=ShoppingListComparisonResponse)
def compare_shopping_list() -> ShoppingListComparisonResponse:
    if not os.getenv("SERPAPI_KEY", "").strip():
        raise HTTPException(status_code=503, detail="Shopping search is not configured (SERPAPI_KEY).")
    results = []
    total_savings = 0.0
    for item in list_shopping_items():
        try:
            alternatives = find_alternatives(
                item["name"],
                item["price"],
                item["brand"],
                allow_similar=item["allow_lower_quality"],
            )
            savings = alternatives[0].potential_savings if alternatives else 0.0
            total_savings += savings
            results.append({
                "item_id": item["id"],
                "name": item["name"],
                "original_price": item["price"],
                "allow_lower_quality": item["allow_lower_quality"],
                "alternatives": alternatives,
                "potential_savings": savings,
            })
        except ShoppingServiceError as exc:
            results.append({
                "item_id": item["id"],
                "name": item["name"],
                "original_price": item["price"],
                "allow_lower_quality": item["allow_lower_quality"],
                "alternatives": [],
                "potential_savings": 0.0,
                "error": str(exc),
            })
    return ShoppingListComparisonResponse(items=results, total_potential_savings=total_savings)
