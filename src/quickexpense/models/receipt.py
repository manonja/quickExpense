"""Models for receipt data extraction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PaymentMethod(str, Enum):
    """Supported payment methods."""

    CASH = "cash"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    CHECK = "check"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class LineItem(BaseModel):
    """Individual line item from a receipt."""

    description: str = Field(..., min_length=1, description="Item description")
    quantity: Decimal = Field(default=Decimal(1), gt=0, description="Item quantity")
    unit_price: Decimal = Field(..., gt=0, description="Price per unit")
    total_price: Decimal = Field(..., gt=0, description="Total price for this line")

    @field_validator("quantity", "unit_price", "total_price", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: Any) -> Decimal:  # noqa: ANN401
        """Convert numeric values to Decimal."""
        if isinstance(v, int | float):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v.strip())
        if isinstance(v, Decimal):
            return v
        msg = f"Invalid type for decimal conversion: {type(v)}"
        raise ValueError(msg)


class ExtractedReceipt(BaseModel):
    """Receipt data extracted from an image."""

    # Vendor information
    vendor_name: str = Field(..., min_length=1, description="Merchant/vendor name")
    vendor_address: str | None = Field(None, description="Vendor address if available")
    vendor_phone: str | None = Field(None, description="Vendor phone if available")

    # Transaction details
    transaction_date: date = Field(..., description="Date of the transaction")
    receipt_number: str | None = Field(None, description="Receipt/invoice number")
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.OTHER,
        description="Payment method used",
    )

    # Line items
    line_items: list[LineItem] = Field(
        default_factory=list,
        description="Individual items on the receipt",
    )

    # Totals
    subtotal: Decimal = Field(..., ge=0, description="Subtotal before tax")
    tax_amount: Decimal = Field(default=Decimal(0), ge=0, description="Tax amount")
    tip_amount: Decimal = Field(default=Decimal(0), ge=0, description="Tip amount")
    total_amount: Decimal = Field(..., gt=0, description="Total amount paid")

    # Additional metadata
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = Field(None, description="Additional notes or context")
    confidence_score: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Confidence score of extraction (0-1)",
    )

    @field_validator(
        "subtotal", "tax_amount", "tip_amount", "total_amount", mode="before"
    )
    @classmethod
    def convert_amounts_to_decimal(cls, v: Any) -> Decimal:  # noqa: ANN401
        """Convert amount values to Decimal."""
        if isinstance(v, int | float):
            return Decimal(str(v))
        if isinstance(v, str):
            # Remove currency symbols and whitespace
            cleaned = v.strip().replace("$", "").replace(",", "")
            return Decimal(cleaned)
        if isinstance(v, Decimal):
            return v
        msg = f"Invalid type for amount conversion: {type(v)}"
        raise ValueError(msg)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        """Ensure currency code is uppercase."""
        return v.upper()

    def to_expense(self, category: str) -> dict[str, Any]:
        """Convert receipt to expense format for QuickBooks."""
        return {
            "vendor_name": self.vendor_name,
            "date": self.transaction_date,
            "amount": self.total_amount,
            "currency": self.currency,
            "category": category,
            "payment_account": self.payment_method.value,
            "description": self._generate_description(),
            "notes": self.notes,
        }

    def _generate_description(self) -> str:
        """Generate a description from line items."""
        if not self.line_items:
            return f"Receipt from {self.vendor_name}"

        # Take first few items for description
        max_display_items = 3
        items = [item.description for item in self.line_items[:max_display_items]]
        if len(self.line_items) > max_display_items:
            items.append(f"and {len(self.line_items) - max_display_items} more items")

        return ", ".join(items)


class ReceiptExtractionRequest(BaseModel):
    """Request model for receipt extraction."""

    image_base64: str = Field(
        ..., description="Base64 encoded file data (image or PDF)"
    )
    category: str = Field(..., description="Expense category to assign")
    additional_context: str | None = Field(
        None,
        description="Additional context to help with extraction",
    )


class ReceiptExtractionResponse(BaseModel):
    """Response model for receipt extraction."""

    receipt: ExtractedReceipt = Field(..., description="Extracted receipt data")
    expense_data: dict[str, Any] = Field(
        ..., description="Formatted data ready for expense creation"
    )
    processing_time: float = Field(..., description="Time taken to process in seconds")
