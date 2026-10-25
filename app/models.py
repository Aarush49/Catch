from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal[
    "groceries", "produce", "dairy", "meat_seafood", "bakery", "beverages",
    "snacks", "household", "personal_care", "health", "electronics",
    "clothing", "restaurant", "entertainment", "transportation", "utilities", "other",
]


class ReceiptItem(BaseModel):
    raw_name: str
    full_name: str
    category: Category
    quantity: Decimal = Decimal("1")
    unit_price: Decimal | None = None
    total_price: Decimal


class ParsedReceipt(BaseModel):
    store_name: str | None = None
    purchase_date: date | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal
    items: list[ReceiptItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("subtotal", "tax", "total")
    @classmethod
    def nonnegative_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("amounts cannot be negative")
        return value


class ReceiptItemOut(ReceiptItem):
    id: str
    receipt_id: str
    purchased_at: str

    model_config = ConfigDict(from_attributes=True)
