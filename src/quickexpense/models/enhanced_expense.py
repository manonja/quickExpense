"""Enhanced expense models for multi-category support."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CategorizedLineItem(BaseModel):
    """Enhanced line item with categorization for multi-category expenses."""

    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    quantity: int = Field(default=1, ge=1)
    category: str = Field(..., min_length=1)
    deductibility_percentage: int = Field(default=100, ge=0, le=100)
    account_mapping: str | None = Field(None)
    tax_treatment: str = Field(default="standard")
    confidence_score: float = Field(default=1.0, ge=0, le=1)
    business_rule_id: str | None = Field(None)

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: Any) -> Decimal:  # noqa: ANN401
        """Convert float to Decimal for precision."""
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v

    @property
    def deductible_amount(self) -> Decimal:
        """Calculate the deductible amount based on percentage and quantity."""
        total_amount = self.amount * self.quantity
        return total_amount * (Decimal(self.deductibility_percentage) / 100)


class MultiCategoryExpense(BaseModel):
    """Enhanced expense model supporting multi-category line items."""

    vendor_name: str = Field(..., min_length=1, max_length=100)
    date: date
    total_amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="CAD", pattern="^[A-Z]{3}$")
    categorized_line_items: list[CategorizedLineItem] = Field(..., min_length=1)

    # Processing metadata
    business_rules_applied: list[str] = Field(default_factory=list)
    total_deductible_amount: Decimal | None = Field(None)
    foreign_exchange_rate: Decimal | None = Field(None)
    payment_method: str = Field(default="unknown")
    payment_account: str | None = Field(None)
    processing_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("total_amount", mode="before")
    @classmethod
    def validate_total_amount(cls, v: Any) -> Decimal:  # noqa: ANN401
        """Convert float to Decimal for precision."""
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v

    @field_validator("foreign_exchange_rate", mode="before")
    @classmethod
    def validate_exchange_rate(cls, v: Any) -> Decimal | None:  # noqa: ANN401
        """Convert exchange rate to Decimal."""
        if v is None:
            return None
        if isinstance(v, float):
            return Decimal(str(v))
        return Decimal(v) if not isinstance(v, Decimal) else v

    def calculate_total_deductible(self) -> Decimal:
        """Calculate total deductible amount from line items."""
        return Decimal(
            str(sum(item.deductible_amount for item in self.categorized_line_items))
        )

    def calculate_line_items_total(self) -> Decimal:
        """Calculate total from line items for validation."""
        return Decimal(
            str(
                sum(item.amount * item.quantity for item in self.categorized_line_items)
            )
        )

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        """Post-initialization validation and calculations."""
        # Auto-calculate total deductible amount if not provided
        if self.total_deductible_amount is None:
            object.__setattr__(
                self, "total_deductible_amount", self.calculate_total_deductible()
            )

        # Validate that line items total matches expense total (within tolerance)
        line_total = self.calculate_line_items_total()
        tolerance = Decimal("0.01")  # 1 cent tolerance for rounding
        if abs(line_total - self.total_amount) > tolerance:
            msg = (
                f"Line items total ({line_total}) does not match "
                f"expense total ({self.total_amount})"
            )
            raise ValueError(msg)

    def get_items_by_category(self, category: str) -> list[CategorizedLineItem]:
        """Get all line items for a specific category."""
        return [
            item for item in self.categorized_line_items if item.category == category
        ]

    def get_categories(self) -> set[str]:
        """Get all unique categories in this expense."""
        return {item.category for item in self.categorized_line_items}

    def get_deductible_amount_by_category(self) -> dict[str, Decimal]:
        """Get deductible amounts grouped by category."""
        category_totals: dict[str, Decimal] = {}
        for item in self.categorized_line_items:
            if item.category not in category_totals:
                category_totals[item.category] = Decimal("0.00")
            category_totals[item.category] += item.deductible_amount
        return category_totals
