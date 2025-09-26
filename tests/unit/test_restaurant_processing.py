"""Unit tests for restaurant receipt processing."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from quickexpense.cli import QuickExpenseCLI
from quickexpense.models.receipt import ExtractedReceipt, LineItem, PaymentMethod


@pytest.fixture
def receipt_processor():
    """Create a receipt processor for testing."""
    processor = QuickExpenseCLI()
    processor.business_rules_engine = Mock()
    return processor


@pytest.fixture
def pho_receipt_data():
    """PHO GEORGIA EXPRESS receipt data."""
    return ExtractedReceipt(
        vendor_name="PHO GEORGIA EXPRESS",
        vendor_address="575 W GEORGIA ST\nVANCOUVER, BC V6B 2A3",
        vendor_phone="6045648828",
        transaction_date=date(2025, 9, 25),
        receipt_number="121694",
        payment_method=PaymentMethod.DEBIT_CARD,
        notes=None,
        line_items=[
            LineItem(
                description="3. Shrimp Salad Rolls",
                quantity=Decimal("1"),
                unit_price=Decimal("11.0"),
                total_price=Decimal("11.0"),
            ),
            LineItem(
                description="52. Lemongrass Pork Sandwich",
                quantity=Decimal("1"),
                unit_price=Decimal("19.0"),
                total_price=Decimal("19.0"),
            ),
        ],
        subtotal=Decimal("30.0"),
        tax_amount=Decimal("1.5"),
        tip_amount=Decimal("4.73"),
        total_amount=Decimal("36.23"),
        currency="CAD",
        confidence_score=0.95,
    )


@pytest.fixture
def marriott_receipt_data():
    """Marriott hotel receipt data (travel context)."""
    return ExtractedReceipt(
        vendor_name="Marriott Downtown",
        vendor_address="123 Hotel St\nToronto, ON M5V 1A1",
        vendor_phone=None,
        transaction_date=date(2025, 9, 20),
        receipt_number=None,
        payment_method=PaymentMethod.CREDIT_CARD,
        notes=None,
        line_items=[
            LineItem(
                description="Room Charge - Deluxe King",
                quantity=Decimal("1"),
                unit_price=Decimal("200.0"),
                total_price=Decimal("200.0"),
            ),
            LineItem(
                description="Restaurant Room Charge",
                quantity=Decimal("1"),
                unit_price=Decimal("45.0"),
                total_price=Decimal("45.0"),
            ),
        ],
        subtotal=Decimal("245.0"),
        tax_amount=Decimal("31.85"),
        total_amount=Decimal("276.85"),
        currency="CAD",
        confidence_score=0.92,
    )


class TestRestaurantDetection:
    """Test restaurant detection logic."""

    def test_detects_pho_restaurant(self, receipt_processor, pho_receipt_data):
        """Test that PHO GEORGIA EXPRESS is detected as restaurant."""
        is_restaurant = receipt_processor._is_local_restaurant(
            pho_receipt_data.vendor_name, pho_receipt_data.line_items
        )
        assert is_restaurant is True

    def test_detects_food_items_as_restaurant(self, receipt_processor):
        """Test detection based on food item descriptions."""
        line_items = [
            Mock(description="Chicken Sandwich"),
            Mock(description="Caesar Salad"),
        ]

        is_restaurant = receipt_processor._is_local_restaurant(
            "Random Food Place", line_items
        )
        assert is_restaurant is True

    def test_various_restaurant_patterns(self, receipt_processor):
        """Test various restaurant name patterns."""
        restaurant_names = [
            "Pizza Hut Express",
            "Sushi Garden",
            "Burger King",
            "Noodle House",
            "Coffee Bean",
            "Local Grill",
            "Taco Bell",
            "Ramen Shop",
        ]

        for name in restaurant_names:
            is_restaurant = receipt_processor._is_local_restaurant(name, [])
            assert is_restaurant is True, f"Failed to detect {name} as restaurant"

    def test_does_not_detect_hotel_as_restaurant(
        self, receipt_processor, marriott_receipt_data
    ):
        """Test that hotel receipts are not detected as local restaurants."""
        is_restaurant = receipt_processor._is_local_restaurant(
            marriott_receipt_data.vendor_name, marriott_receipt_data.line_items
        )
        assert is_restaurant is False

    def test_does_not_detect_office_supplies_as_restaurant(self, receipt_processor):
        """Test that office supply receipts are not detected as restaurants."""
        line_items = [
            Mock(description="Printer Paper"),
            Mock(description="Stapler"),
        ]

        is_restaurant = receipt_processor._is_local_restaurant(
            "Staples Business Depot", line_items
        )
        assert is_restaurant is False


class TestRestaurantConsolidatedProcessing:
    """Test consolidated restaurant processing."""

    def test_consolidates_pho_receipt(self, receipt_processor, pho_receipt_data):
        """Test PHO receipt gets consolidated into 2 lines."""
        _rule_applications, categorized_items = (
            receipt_processor._process_restaurant_consolidated(
                line_items=pho_receipt_data.line_items,
                tax_amount=pho_receipt_data.tax_amount,
                tip_amount=pho_receipt_data.tip_amount,
            )
        )

        # Should have exactly 2 line items
        assert len(categorized_items) == 2

        # First item: Meals & Entertainment (food + tip)
        meal_item = categorized_items[0]
        assert meal_item.category == "Meals & Entertainment"
        assert meal_item.amount == Decimal("34.73")  # $30 food + $4.73 tip
        assert meal_item.deductibility_percentage == 50
        assert meal_item.tax_treatment == "meals_limitation"
        assert "Business meal" in meal_item.description
        assert "Shrimp Salad Rolls" in meal_item.description
        assert "Lemongrass Pork Sandwich" in meal_item.description

        # Second item: GST/HST
        gst_item = categorized_items[1]
        assert gst_item.category == "Tax-GST/HST"
        assert gst_item.amount == Decimal("1.5")
        assert gst_item.deductibility_percentage == 100
        assert gst_item.tax_treatment == "input_tax_credit"
        assert gst_item.description == "GST - Input Tax Credit"

        # Total should match original receipt
        total = sum(item.amount for item in categorized_items)
        assert total == pho_receipt_data.total_amount

    def test_correct_rule_applications_reporting(
        self, receipt_processor, pho_receipt_data
    ):
        """Test that rule applications are reported correctly for restaurants."""
        rule_applications, _ = receipt_processor._process_restaurant_consolidated(
            line_items=pho_receipt_data.line_items,
            tax_amount=pho_receipt_data.tax_amount,
            tip_amount=pho_receipt_data.tip_amount,
        )

        # Should have 2 rule applications
        assert len(rule_applications) == 2

        # First rule: Restaurant meal
        meal_rule = rule_applications[0]
        assert meal_rule["id"] == "local_restaurant_meal"
        assert meal_rule["name"] == "Local Restaurant Meal"
        assert meal_rule["rule_applied"] == "Local Restaurant Detection"
        assert meal_rule["confidence"] == 0.95
        assert meal_rule["category"] == "Meals & Entertainment"
        assert meal_rule["deductibility_percentage"] == 50
        assert meal_rule["items_affected"] == 2  # Both food items
        assert meal_rule["is_fallback"] is False

        # Second rule: GST
        gst_rule = rule_applications[1]
        assert gst_rule["id"] == "gst_hst_charges"
        assert gst_rule["name"] == "GST/HST Tax Charges"
        assert gst_rule["confidence"] == 1.0
        assert gst_rule["category"] == "Tax-GST/HST"
        assert gst_rule["deductibility_percentage"] == 100

    def test_handles_receipt_with_no_tip(self, receipt_processor):
        """Test restaurant processing with no tip."""
        line_items = [
            Mock(description="Chicken Burger", total_price=Decimal("15.0")),
        ]

        _rule_applications, categorized_items = (
            receipt_processor._process_restaurant_consolidated(
                line_items=line_items,
                tax_amount=Decimal("2.25"),
                tip_amount=Decimal("0"),  # No tip
            )
        )

        # Should still have 2 items: meal + GST
        assert len(categorized_items) == 2

        # Meal item should be just food amount (no tip)
        meal_item = categorized_items[0]
        assert meal_item.amount == Decimal("15.0")  # Just food, no tip

    def test_handles_receipt_with_no_tax(self, receipt_processor):
        """Test restaurant processing with no GST."""
        line_items = [
            Mock(description="Coffee", total_price=Decimal("5.0")),
        ]

        _rule_applications, categorized_items = (
            receipt_processor._process_restaurant_consolidated(
                line_items=line_items,
                tax_amount=Decimal("0"),  # No GST
                tip_amount=Decimal("1.0"),
            )
        )

        # Should have only 1 item: meal + tip (no GST item)
        assert len(categorized_items) == 1

        # Should have only 1 rule application: meal (no GST rule)
        assert len(_rule_applications) == 1
        assert _rule_applications[0]["id"] == "local_restaurant_meal"


class TestPaymentMethodPreservation:
    """Test that payment method is preserved through processing."""

    def test_preserves_debit_card_payment_method(
        self, receipt_processor, pho_receipt_data
    ):
        """Test that DEBIT_CARD payment method is preserved."""
        _rule_applications, _categorized_items, enhanced_expense = (
            receipt_processor._apply_business_rules(pho_receipt_data)
        )

        assert enhanced_expense.payment_method == "debit_card"

    def test_handles_various_payment_method_formats(self, receipt_processor):
        """Test various payment method string formats are handled correctly."""
        # Test enum format
        receipt_data = {
            "vendor_name": "Test Restaurant",
            "total_amount": 20.0,
            "date": date(2025, 9, 25),
            "currency": "CAD",
            "line_items": [{"description": "Food", "amount": 18.0}],
            "tax_amount": 2.0,
            "tip_amount": 0.0,
            "payment_method": "<PaymentMethod.CREDIT_CARD: 'credit_card'>",
        }

        _rule_applications, _categorized_items, enhanced_expense = (
            receipt_processor._apply_business_rules(receipt_data)
        )

        assert enhanced_expense.payment_method == "credit_card"


class TestBusinessRulesIntegration:
    """Test integration between new restaurant logic and existing business rules."""

    def test_restaurant_bypasses_individual_item_rules(
        self, receipt_processor, pho_receipt_data
    ):
        """Test restaurant receipts bypass individual item business rules."""
        # Mock the business rules engine - NOT called for restaurant receipts
        receipt_processor.business_rules_engine.categorize_line_items = Mock()

        _rule_applications, categorized_items, _enhanced_expense = (
            receipt_processor._apply_business_rules(pho_receipt_data)
        )

        # categorize_line_items should NOT have been called for restaurant receipt
        receipt_processor.business_rules_engine.categorize_line_items.assert_not_called()

        # Should get consolidated restaurant processing instead
        assert len(categorized_items) == 2
        assert categorized_items[0].category == "Meals & Entertainment"
        assert categorized_items[1].category == "Tax-GST/HST"

    def test_non_restaurant_uses_regular_rules(
        self, receipt_processor, marriott_receipt_data
    ):
        """Test non-restaurant receipts use regular business rules."""
        # Mock the business rules engine - SHOULD be called for non-restaurant

        mock_results = [
            Mock(
                business_rule_id="hotel_accommodation",
                rule_applied=Mock(name="Hotel Accommodation"),
                confidence_score=0.9,
                category="Travel-Lodging",
                qb_account="Travel - Lodging",
                deductibility_percentage=100,
                account_mapping="Travel - Lodging",
                tax_treatment="standard",
                is_fallback=False,
            ),
            Mock(
                business_rule_id="room_service_meals",
                rule_applied=Mock(name="Room Service Meals"),
                confidence_score=0.8,
                category="Travel-Meals",
                qb_account="Travel - Meals & Entertainment",
                deductibility_percentage=50,
                account_mapping="Travel - Meals & Entertainment",
                tax_treatment="meals_limitation",
                is_fallback=False,
            ),
        ]

        receipt_processor.business_rules_engine.categorize_line_items.return_value = (
            mock_results
        )

        _rule_applications, categorized_items, _enhanced_expense = (
            receipt_processor._apply_business_rules(marriott_receipt_data)
        )

        # categorize_line_items SHOULD have been called for non-restaurant receipt
        receipt_processor.business_rules_engine.categorize_line_items.assert_called_once()

        # Should use regular processing, not consolidated
        assert (
            len(categorized_items) >= 2
        )  # Regular processing + potential tax/tip items


class TestTaxDeductibilityCalculations:
    """Test tax deductibility calculations for restaurant receipts."""

    def test_correct_deductibility_calculation(
        self, receipt_processor, pho_receipt_data
    ):
        """Test that deductibility is calculated correctly for restaurant receipts."""
        _rule_applications, _categorized_items, _enhanced_expense = (
            receipt_processor._apply_business_rules(pho_receipt_data)
        )

        # Calculate expected deductible amount
        meal_deductible = Decimal("34.73") * Decimal("0.5")  # 50% of meals
        gst_deductible = Decimal("1.5")  # 100% of GST
        expected_total_deductible = meal_deductible + gst_deductible

        actual_total_deductible = _enhanced_expense.calculate_total_deductible()

        assert actual_total_deductible == expected_total_deductible

        # Should be approximately 52.1% overall deductibility
        deductibility_rate = float(actual_total_deductible) / float(
            _enhanced_expense.total_amount
        )
        assert abs(deductibility_rate - 0.521) < 0.01  # Within 1% tolerance
