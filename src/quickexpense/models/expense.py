"""Expense models using Pydantic v2."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class LineItem(BaseModel):
    """Basic line item for backward compatibility."""

    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    quantity: int = Field(default=1, ge=1)

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: Any) -> Decimal:  # noqa: ANN401
        """Convert float to Decimal for precision."""
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v

    def to_categorized(
        self, category: str, deductibility_percentage: int = 100, **kwargs: Any
    ) -> "CategorizedLineItem":
        """Convert basic line item to categorized line item."""
        from .enhanced_expense import CategorizedLineItem

        return CategorizedLineItem(
            description=self.description,
            amount=self.amount,
            quantity=self.quantity,
            category=category,
            deductibility_percentage=deductibility_percentage,
            **kwargs,
        )


class Expense(BaseModel):
    """Single-category expense model for backward compatibility."""

    vendor_name: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    date: date
    currency: str = Field(default="CAD", pattern="^[A-Z]{3}$")
    category: str = Field(..., min_length=1)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    line_items: list[LineItem] | None = None

    @field_validator("amount", "tax_amount", mode="before")
    @classmethod
    def validate_decimal_fields(cls, v: Any) -> Decimal:  # noqa: ANN401
        """Convert float to Decimal for precision."""
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v

    @field_validator("tax_amount")
    @classmethod
    def validate_tax_amount(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        """Ensure tax amount doesn't exceed total amount."""
        if info.data and "amount" in info.data and v > info.data["amount"]:
            msg = "Tax amount cannot exceed total amount"
            raise ValueError(msg)
        return v

    def to_multi_category(
        self, deductibility_percentage: int = 100, **kwargs: Any
    ) -> "MultiCategoryExpense":
        """Convert single-category expense to multi-category format."""
        from .enhanced_expense import CategorizedLineItem, MultiCategoryExpense

        # Create single categorized line item
        main_item = CategorizedLineItem(
            description=self.category,
            amount=self.amount - self.tax_amount,
            category=self.category,
            deductibility_percentage=deductibility_percentage,
            **kwargs,
        )

        categorized_items = [main_item]

        # Add tax as separate line item if present
        if self.tax_amount > 0:
            tax_item = CategorizedLineItem(
                description="Tax",
                amount=self.tax_amount,
                category="Tax-GST",
                deductibility_percentage=100,
                tax_treatment="input_tax_credit",
            )
            categorized_items.append(tax_item)

        return MultiCategoryExpense(
            vendor_name=self.vendor_name,
            date=self.date,
            total_amount=self.amount,
            currency=self.currency,
            categorized_line_items=categorized_items,
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "vendor_name": "Office Depot",
                    "amount": 45.99,
                    "date": "2024-01-15",
                    "currency": "CAD",
                    "category": "Office Supplies",
                    "tax_amount": 3.42,
                }
            ]
        }
    }
