"""Tests for enhanced multi-category expense models."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quickexpense.models import CategorizedLineItem, Expense, MultiCategoryExpense


class TestCategorizedLineItem:
    """Tests for CategorizedLineItem model."""

    def test_basic_categorized_line_item(self):
        """Test basic categorized line item creation."""
        item = CategorizedLineItem(
            description="Room Charge",
            amount=Decimal("175.00"),
            category="Travel-Lodging",
            deductibility_percentage=100,
        )

        assert item.description == "Room Charge"
        assert item.amount == Decimal("175.00")
        assert item.category == "Travel-Lodging"
        assert item.deductibility_percentage == 100
        assert item.tax_treatment == "standard"
        assert item.confidence_score == 1.0
        assert item.deductible_amount == Decimal("175.00")

    def test_partial_deductibility(self):
        """Test line item with partial deductibility."""
        item = CategorizedLineItem(
            description="Restaurant Charge",
            amount=Decimal("50.00"),
            category="Travel-Meals",
            deductibility_percentage=50,
            tax_treatment="meals_limitation",
        )

        assert item.deductible_amount == Decimal("25.00")
        assert item.tax_treatment == "meals_limitation"

    def test_zero_deductibility(self):
        """Test line item with zero deductibility."""
        item = CategorizedLineItem(
            description="Personal Item",
            amount=Decimal("20.00"),
            category="Personal",
            deductibility_percentage=0,
        )

        assert item.deductible_amount == Decimal("0.00")

    def test_validation_errors(self):
        """Test validation errors for invalid data."""
        # Invalid deductibility percentage
        with pytest.raises(ValidationError):
            CategorizedLineItem(
                description="Test",
                amount=Decimal("10.00"),
                category="Test",
                deductibility_percentage=150,  # Invalid: > 100
            )

        # Negative amount
        with pytest.raises(ValidationError):
            CategorizedLineItem(
                description="Test", amount=Decimal("-10.00"), category="Test"
            )

        # Empty description
        with pytest.raises(ValidationError):
            CategorizedLineItem(
                description="", amount=Decimal("10.00"), category="Test"
            )

    def test_confidence_score_validation(self):
        """Test confidence score validation."""
        # Valid confidence score
        item = CategorizedLineItem(
            description="Test",
            amount=Decimal("10.00"),
            category="Test",
            confidence_score=0.85,
        )
        assert item.confidence_score == 0.85

        # Invalid confidence score
        with pytest.raises(ValidationError):
            CategorizedLineItem(
                description="Test",
                amount=Decimal("10.00"),
                category="Test",
                confidence_score=1.5,  # Invalid: > 1.0
            )


class TestMultiCategoryExpense:
    """Tests for MultiCategoryExpense model."""

    def create_marriott_hotel_expense(self) -> MultiCategoryExpense:
        """Create a test Marriott hotel expense."""
        return MultiCategoryExpense(
            vendor_name="Courtyard by Marriott Edmonton",
            date=date(2025, 4, 24),
            total_amount=Decimal("231.92"),
            currency="CAD",
            categorized_line_items=[
                CategorizedLineItem(
                    description="Room Charge",
                    amount=Decimal("175.00"),
                    category="Travel-Lodging",
                    deductibility_percentage=100,
                ),
                CategorizedLineItem(
                    description="Restaurant Room Charge",
                    amount=Decimal("40.70"),
                    category="Travel-Meals",
                    deductibility_percentage=50,
                    tax_treatment="meals_limitation",
                ),
                CategorizedLineItem(
                    description="Tourism Levy",
                    amount=Decimal("7.21"),
                    category="Travel-Lodging",
                    deductibility_percentage=100,
                ),
                CategorizedLineItem(
                    description="GST",
                    amount=Decimal("9.01"),
                    category="Tax-GST",
                    deductibility_percentage=100,
                    tax_treatment="input_tax_credit",
                ),
            ],
        )

    def test_marriott_hotel_expense(self):
        """Test Marriott hotel bill processing."""
        expense = self.create_marriott_hotel_expense()

        assert expense.vendor_name == "Courtyard by Marriott Edmonton"
        assert expense.total_amount == Decimal("231.92")
        assert len(expense.categorized_line_items) == 4

        # Check total deductible calculation
        expected_deductible = (
            Decimal("175.00") + Decimal("20.35") + Decimal("7.21") + Decimal("9.01")
        )
        assert expense.calculate_total_deductible() == expected_deductible
        assert expense.total_deductible_amount == expected_deductible

    def test_get_categories(self):
        """Test getting unique categories."""
        expense = self.create_marriott_hotel_expense()
        categories = expense.get_categories()

        assert categories == {"Travel-Lodging", "Travel-Meals", "Tax-GST"}

    def test_get_items_by_category(self):
        """Test getting items by category."""
        expense = self.create_marriott_hotel_expense()

        lodging_items = expense.get_items_by_category("Travel-Lodging")
        assert len(lodging_items) == 2  # Room charge + tourism levy
        assert sum(item.amount for item in lodging_items) == Decimal("182.21")

    def test_get_deductible_amount_by_category(self):
        """Test getting deductible amounts by category."""
        expense = self.create_marriott_hotel_expense()
        deductible_by_category = expense.get_deductible_amount_by_category()

        assert deductible_by_category["Travel-Lodging"] == Decimal("182.21")
        assert deductible_by_category["Travel-Meals"] == Decimal("20.35")
        assert deductible_by_category["Tax-GST"] == Decimal("9.01")

    def test_line_items_total_validation(self):
        """Test validation that line items total matches expense total."""
        # Valid expense (totals match)
        valid_expense = MultiCategoryExpense(
            vendor_name="Test Vendor",
            date=date(2025, 1, 15),
            total_amount=Decimal("100.00"),
            categorized_line_items=[
                CategorizedLineItem(
                    description="Item 1", amount=Decimal("60.00"), category="Category1"
                ),
                CategorizedLineItem(
                    description="Item 2", amount=Decimal("40.00"), category="Category2"
                ),
            ],
        )
        assert valid_expense.calculate_line_items_total() == Decimal("100.00")

        # Invalid expense (totals don't match)
        with pytest.raises(ValidationError, match="Line items total.*does not match"):
            MultiCategoryExpense(
                vendor_name="Test Vendor",
                date=date(2025, 1, 15),
                total_amount=Decimal("100.00"),
                categorized_line_items=[
                    CategorizedLineItem(
                        description="Item 1",
                        amount=Decimal("60.00"),
                        category="Category1",
                    ),
                    CategorizedLineItem(
                        description="Item 2",
                        amount=Decimal("30.00"),  # Total only 90.00
                        category="Category2",
                    ),
                ],
            )

    def test_foreign_exchange_handling(self):
        """Test foreign exchange rate handling."""
        expense = MultiCategoryExpense(
            vendor_name="USD Vendor",
            date=date(2025, 1, 15),
            total_amount=Decimal("100.00"),
            currency="CAD",
            foreign_exchange_rate=Decimal("1.35"),
            categorized_line_items=[
                CategorizedLineItem(
                    description="Test Item", amount=Decimal("100.00"), category="Test"
                )
            ],
        )

        assert expense.foreign_exchange_rate == Decimal("1.35")

    def test_business_rules_tracking(self):
        """Test business rules tracking."""
        expense = MultiCategoryExpense(
            vendor_name="Test Vendor",
            date=date(2025, 1, 15),
            total_amount=Decimal("50.00"),
            business_rules_applied=["hotel_accommodation", "restaurant_meals"],
            categorized_line_items=[
                CategorizedLineItem(
                    description="Test Item",
                    amount=Decimal("50.00"),
                    category="Test",
                    business_rule_id="hotel_accommodation",
                )
            ],
        )

        assert "hotel_accommodation" in expense.business_rules_applied
        assert "restaurant_meals" in expense.business_rules_applied


class TestExpenseBackwardCompatibility:
    """Tests for backward compatibility with original Expense model."""

    def test_single_category_expense(self):
        """Test original single-category expense model."""
        expense = Expense(
            vendor_name="Office Depot",
            amount=Decimal("45.99"),
            date=date(2024, 1, 15),
            currency="CAD",
            category="Office Supplies",
            tax_amount=Decimal("3.42"),
        )

        assert expense.vendor_name == "Office Depot"
        assert expense.amount == Decimal("45.99")
        assert expense.tax_amount == Decimal("3.42")

    def test_conversion_to_multi_category(self):
        """Test conversion from single to multi-category expense."""
        expense = Expense(
            vendor_name="Office Depot",
            amount=Decimal("45.99"),
            date=date(2024, 1, 15),
            category="Office Supplies",
            tax_amount=Decimal("3.42"),
        )

        multi_expense = expense.to_multi_category(deductibility_percentage=100)

        assert multi_expense.vendor_name == "Office Depot"
        assert multi_expense.total_amount == Decimal("45.99")
        assert len(multi_expense.categorized_line_items) == 2  # Main item + tax

        # Check main item
        main_item = multi_expense.categorized_line_items[0]
        assert main_item.category == "Office Supplies"
        assert main_item.amount == Decimal("42.57")  # 45.99 - 3.42
        assert main_item.deductibility_percentage == 100

        # Check tax item
        tax_item = multi_expense.categorized_line_items[1]
        assert tax_item.category == "Tax-GST"
        assert tax_item.amount == Decimal("3.42")
        assert tax_item.tax_treatment == "input_tax_credit"

    def test_line_item_conversion(self):
        """Test LineItem to CategorizedLineItem conversion."""
        from quickexpense.models import LineItem

        line_item = LineItem(description="Paper", amount=Decimal("25.00"), quantity=2)

        categorized = line_item.to_categorized(
            category="Office Supplies", deductibility_percentage=100
        )

        assert categorized.description == "Paper"
        assert categorized.amount == Decimal("25.00")
        assert categorized.quantity == 2
        assert categorized.category == "Office Supplies"
        assert categorized.deductibility_percentage == 100


class TestValidationEdgeCases:
    """Test edge cases and validation scenarios."""

    def test_rounding_tolerance(self):
        """Test that small rounding differences are tolerated."""
        # Should pass with 1 cent tolerance
        expense = MultiCategoryExpense(
            vendor_name="Test Vendor",
            date=date(2025, 1, 15),
            total_amount=Decimal("100.00"),
            categorized_line_items=[
                CategorizedLineItem(
                    description="Item 1", amount=Decimal("33.33"), category="Category1"
                ),
                CategorizedLineItem(
                    description="Item 2", amount=Decimal("33.33"), category="Category2"
                ),
                CategorizedLineItem(
                    description="Item 3",
                    amount=Decimal("33.34"),  # 99.99 + 0.01 tolerance
                    category="Category3",
                ),
            ],
        )

        assert expense.calculate_line_items_total() == Decimal("100.00")

    def test_quantity_calculations(self):
        """Test calculations with quantities > 1."""
        expense = MultiCategoryExpense(
            vendor_name="Test Vendor",
            date=date(2025, 1, 15),
            total_amount=Decimal("150.00"),
            categorized_line_items=[
                CategorizedLineItem(
                    description="Paper",
                    amount=Decimal("25.00"),
                    quantity=3,  # 75.00 total
                    category="Office Supplies",
                ),
                CategorizedLineItem(
                    description="Pens",
                    amount=Decimal("15.00"),
                    quantity=5,  # 75.00 total
                    category="Office Supplies",
                ),
            ],
        )

        assert expense.calculate_line_items_total() == Decimal("150.00")
        assert expense.calculate_total_deductible() == Decimal("150.00")

    def test_currency_validation(self):
        """Test currency code validation."""
        # Valid currency
        expense = MultiCategoryExpense(
            vendor_name="Test Vendor",
            date=date(2025, 1, 15),
            total_amount=Decimal("100.00"),
            currency="USD",
            categorized_line_items=[
                CategorizedLineItem(
                    description="Test", amount=Decimal("100.00"), category="Test"
                )
            ],
        )
        assert expense.currency == "USD"

        # Invalid currency (too long)
        with pytest.raises(ValidationError):
            MultiCategoryExpense(
                vendor_name="Test Vendor",
                date=date(2025, 1, 15),
                total_amount=Decimal("100.00"),
                currency="INVALID",  # Too long
                categorized_line_items=[
                    CategorizedLineItem(
                        description="Test", amount=Decimal("100.00"), category="Test"
                    )
                ],
            )
