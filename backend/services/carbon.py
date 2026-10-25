"""Illustrative kg CO2e per USD factors for demo-level estimates."""

from decimal import Decimal

EMISSION_FACTORS: dict[str, Decimal] = {
    "groceries": Decimal("0.09"),
    "produce": Decimal("0.08"),
    "dairy": Decimal("0.20"),
    "meat_seafood": Decimal("0.80"),
    "bakery": Decimal("0.10"),
    "beverages": Decimal("0.12"),
    "snacks": Decimal("0.12"),
    "household": Decimal("0.14"),
    "personal_care": Decimal("0.14"),
    "health": Decimal("0.12"),
    "electronics": Decimal("0.45"),
    "clothing": Decimal("0.30"),
    "restaurant": Decimal("0.18"),
    "entertainment": Decimal("0.08"),
    "transportation": Decimal("0.24"),
    "utilities": Decimal("0.32"),
    "other": Decimal("0.12"),
}


def estimate_carbon(price: Decimal, category: str) -> Decimal:
    return (price * EMISSION_FACTORS.get(category, EMISSION_FACTORS["other"])).quantize(Decimal("0.01"))
