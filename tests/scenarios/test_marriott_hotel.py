"""Test scenario: Marriott hotel bill processing with vendor-aware business rules.

This test validates the critical user feedback issue that was resolved:
Marketing fees from hotels should be categorized as Travel-Lodging, not
Professional Services.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from quickexpense.models.business_rules import ExpenseContext
from quickexpense.models.expense import LineItem
from quickexpense.services.business_rules import BusinessRuleEngine


@pytest.fixture
def marriott_line_items() -> list[LineItem]:
    """Create Marriott hotel bill line items with marketing fees (critical case)."""
    return [
        LineItem(
            description="Room Charge",
            amount=Decimal("350.00"),
        ),
        LineItem(
            description="Marketing Fee",  # This is the critical test case
            amount=Decimal("25.00"),
        ),
        LineItem(
            description="Restaurant Room Charge",
            amount=Decimal("142.52"),
        ),
        LineItem(
            description="GST",
            amount=Decimal("18.02"),
        ),
    ]


class TestMarriottHotelBusinessScenario:
    """Test the complete Marriott hotel business scenario.

    This validates that our vendor-aware business rules correctly handle
    the user feedback issue: marketing fees from hotels should be categorized
    as Travel-Lodging, not Professional Services.
    """

    def test_marriott_marketing_fee_vendor_aware_categorization(
        self,
        marriott_line_items: list[LineItem],
    ) -> None:
        """Test that marketing fees from hotels are categorized as Travel-Lodging.

        This is the core test that validates our vendor-aware business rules fix.
        Before the fix: Marketing Fee → Professional Services (85% confidence)
        After the fix: Marketing Fee → Travel-Lodging (95%+ confidence)
        """
        # Load the real business rules configuration
        from pathlib import Path

        config_path = (
            Path(__file__).parent.parent.parent / "config" / "business_rules.json"
        )
        if not config_path.exists():
            pytest.skip("Business rules configuration not found")

        engine = BusinessRuleEngine(config_path)

        # Create context with vendor information for vendor-aware categorization
        from datetime import datetime

        context = ExpenseContext(
            vendor_name="Courtyard by Marriott Edmonton",
            business_purpose="consulting",
            transaction_date=datetime.fromisoformat("2024-04-24"),
            total_amount=Decimal("535.54"),
            payment_method="credit_card",
            location="Edmonton",
        )

        # Process the Marriott expense through business rules
        results = engine.categorize_line_items(marriott_line_items, context)

        # Verify we got results for all line items
        assert len(results) == 4

        # Room Charge: Should be Travel-Lodging
        room_result = results[0]
        assert room_result.category == "Travel-Lodging"
        assert room_result.deductibility_percentage == 100
        assert not room_result.is_fallback

        # Marketing Fee: THE CRITICAL TEST - Should be Travel-Lodging for hotels
        marketing_result = results[1]
        assert (
            marketing_result.category == "Travel-Lodging"
        )  # NOT Professional Services!
        assert marketing_result.deductibility_percentage == 100
        assert not marketing_result.is_fallback
        assert (
            marketing_result.confidence_score >= 0.9
        )  # High confidence due to vendor context

        # Restaurant Room Charge: Should be Travel-Meals with 50% deductibility
        meal_result = results[2]
        assert meal_result.category == "Travel-Meals"
        assert meal_result.deductibility_percentage == 50

        # GST: Should be Tax-GST/HST
        gst_result = results[3]
        assert gst_result.category == "Tax-GST/HST"
        assert gst_result.deductibility_percentage == 100

    def test_marriott_scenario_demonstrates_vendor_context_value(
        self,
        marriott_line_items: list[LineItem],
    ) -> None:
        """Test that vendor context significantly improves categorization accuracy."""
        from pathlib import Path

        config_path = (
            Path(__file__).parent.parent.parent / "config" / "business_rules.json"
        )
        if not config_path.exists():
            pytest.skip("Business rules configuration not found")

        engine = BusinessRuleEngine(config_path)

        # Get the marketing fee line item specifically
        marketing_line_item = marriott_line_items[1]
        assert marketing_line_item.description == "Marketing Fee"

        # Process WITHOUT vendor context (simulating old behavior)
        result_without_vendor = engine.categorize_line_item(marketing_line_item)

        # Process WITH vendor context (new vendor-aware behavior)
        from datetime import datetime

        context = ExpenseContext(
            vendor_name="Courtyard by Marriott Edmonton",
            transaction_date=datetime.fromisoformat("2024-04-24"),
            total_amount=Decimal("25.00"),
            payment_method="credit_card",
            business_purpose="business_travel",
            location="Edmonton",
        )
        result_with_vendor = engine.categorize_line_item(marketing_line_item, context)

        # With vendor context should be Travel-Lodging with higher confidence
        assert result_with_vendor.category == "Travel-Lodging"
        assert (
            result_with_vendor.confidence_score > result_without_vendor.confidence_score
        )
