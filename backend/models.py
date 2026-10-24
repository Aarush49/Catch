"""Public shopping response models."""

from typing import Literal

from pydantic import BaseModel, Field


class ShoppingProduct(BaseModel):
    title: str
    price: float = Field(gt=0, allow_inf_nan=False, description="Listed price in USD")
    source: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5, allow_inf_nan=False)
    link: str
    thumbnail: str | None = None
    product_id: str | None = None


class ShoppingAlternative(ShoppingProduct):
    match_type: Literal["exact_title_match", "similar_alternative"]
    match_reason: str
    potential_savings: float = Field(gt=0, allow_inf_nan=False)
    potential_savings_percent: float = Field(ge=0, le=100, allow_inf_nan=False)


class ShoppingAlternativesResponse(BaseModel):
    query: str
    original_price: float = Field(gt=0, allow_inf_nan=False)
    alternatives: list[ShoppingAlternative]
    currency: Literal["USD"] = "USD"
    savings_note: str = (
        "Potential savings compare listing prices only. Product equivalence is not "
        "verified; check model, size, quantity, condition, and seller. Shipping and "
        "taxes may be additional, and the original price may include different costs."
    )
