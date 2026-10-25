"""Public shopping response models."""

from datetime import date as Date
from decimal import Decimal
from typing import Literal
from uuid import UUID

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


ExpenseCategory = Literal[
    "groceries", "produce", "dairy", "meat_seafood", "bakery", "beverages",
    "snacks", "household", "personal_care", "health", "electronics",
    "clothing", "restaurant", "entertainment", "transportation", "utilities", "other",
]


class ReceiptLine(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    category: ExpenseCategory


class ParsedReceipt(BaseModel):
    store: str | None = Field(default=None, max_length=200)
    date: Date | None = None
    total: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    items: list[ReceiptLine] = Field(default_factory=list, max_length=200)


class ShoppingListItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0, allow_inf_nan=False)
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    category: ExpenseCategory = "other"
    allow_lower_quality: bool = False


class NessieLinkRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=100)
    account_id: str = Field(min_length=1, max_length=100)


class SavingsMoveRequest(BaseModel):
    amount: float = Field(gt=0, le=100_000, allow_inf_nan=False)
    description: str = Field(default="Swap savings", min_length=1, max_length=200)


class PredictionRequest(BaseModel):
    amount: float = Field(gt=0, allow_inf_nan=False)
    years: int = Field(default=30, ge=1, le=100)
    alternative_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    times_per_month: int | None = Field(default=None, ge=1, le=1000)
    annual_return: float = Field(default=0.07, ge=0, le=1, allow_inf_nan=False)


class ShoppingComparisonItem(BaseModel):
    item_id: UUID
    name: str
    original_price: float | None
    allow_lower_quality: bool
    alternatives: list[ShoppingAlternative]
    potential_savings: float = Field(ge=0, allow_inf_nan=False)
    error: str | None = None


class ShoppingListComparisonResponse(BaseModel):
    items: list[ShoppingComparisonItem]
    total_potential_savings: float = Field(ge=0, allow_inf_nan=False)
    currency: Literal["USD"] = "USD"
