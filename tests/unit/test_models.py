"""Unit tests for models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quickexpense.models import Expense, LineItem


class TestLineItem:
    """Test LineItem model."""

    def test_valid_line_item(self) -> None:
        """Test creating a valid line item."""
        item = LineItem(
            description="Office Supplies",
            amount=Decimal("25.99"),
            quantity=2,
        )
        assert item.description == "Office Supplies"
        assert item.amount == Decimal("25.99")
        assert item.quantity == 2

    def test_amount_from_float(self) -> None:
        """Test amount conversion from float."""
        item = LineItem(description="Test", amount=25.99)
        assert isinstance(item.amount, Decimal)
        assert item.amount == Decimal("25.99")

    def test_invalid_amount(self) -> None:
        """Test invalid amount validation."""
        with pytest.raises(ValidationError):
            LineItem(description="Test", amount=0)

    def test_invalid_quantity(self) -> None:
        """Test invalid quantity validation."""
        with pytest.raises(ValidationError):
            LineItem(description="Test", amount=10, quantity=0)


class TestExpense:
    """Test Expense model."""

    def test_valid_expense(self) -> None:
        """Test creating a valid expense."""
        expense = Expense(
            vendor_name="Office Depot",
            amount=Decimal("45.99"),
            date=date(2024, 1, 15),
            currency="USD",
            category="Office Supplies",
            tax_amount=Decimal("3.42"),
        )
        assert expense.vendor_name == "Office Depot"
        assert expense.amount == Decimal("45.99")
        assert expense.tax_amount == Decimal("3.42")

    def test_default_values(self) -> None:
        """Test default values."""
        expense = Expense(
            vendor_name="Test Vendor",
            amount=100,
            date=date.today(),
            category="Test",
        )
        assert expense.currency == "USD"
        assert expense.tax_amount == Decimal("0.00")

    def test_tax_exceeds_amount(self) -> None:
        """Test tax amount exceeding total amount."""
        with pytest.raises(ValidationError) as exc_info:
            Expense(
                vendor_name="Test",
                amount=100,
                date=date.today(),
                category="Test",
                tax_amount=150,
            )
        assert "Tax amount cannot exceed total amount" in str(exc_info.value)

    def test_invalid_currency_format(self) -> None:
        """Test invalid currency format."""
        with pytest.raises(ValidationError):
            Expense(
                vendor_name="Test",
                amount=100,
                date=date.today(),
                category="Test",
                currency="US",  # Should be 3 characters
            )
