"""Expense models using Pydantic v2."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from typing import Any


class LineItem(BaseModel):
    """Represents a line item in an expense."""

    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    quantity: int = Field(default=1, ge=1)

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: Any) -> Decimal:
        """Convert float to Decimal for precision."""
        if isinstance(v, float):
            return Decimal(str(v))
        return v


class Expense(BaseModel):
    """Represents an expense to be submitted to QuickBooks."""

    vendor_name: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    date: date
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    category: str = Field(..., min_length=1)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    line_items: list[LineItem] | None = None

    @field_validator("amount", "tax_amount", mode="before")
    @classmethod
    def validate_decimal_fields(cls, v: Any) -> Decimal:
        """Convert float to Decimal for precision."""
        if isinstance(v, float):
            return Decimal(str(v))
        return v

    @field_validator("tax_amount")
    @classmethod
    def validate_tax_amount(cls, v: Decimal, info: Any) -> Decimal:
        """Ensure tax amount doesn't exceed total amount."""
        if info.data and "amount" in info.data and v > info.data["amount"]:
            msg = "Tax amount cannot exceed total amount"
            raise ValueError(msg)
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "vendor_name": "Office Depot",
                    "amount": 45.99,
                    "date": "2024-01-15",
                    "currency": "USD",
                    "category": "Office Supplies",
                    "tax_amount": 3.42,
                }
            ]
        }
    }
