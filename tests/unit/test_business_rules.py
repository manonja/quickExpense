"""Tests for the business rules engine and models."""

from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from quickexpense.models.business_rules import (
    BusinessRule,
    ExpenseContext,
    RuleActions,
    RuleConditions,
    TaxTreatment,
)
from quickexpense.models.expense import LineItem
from quickexpense.services.business_rules import (
    BusinessRuleEngine,
    RuleConfigurationError,
)


class TestRuleConditions:
    """Tests for RuleConditions model."""

    def test_create_rule_conditions(self):
        """Test creating rule conditions with various parameters."""
        conditions = RuleConditions(
            description_keywords=["hotel", "room"],
            vendor_patterns=["*hotel*"],
            amount_min=Decimal("50.00"),
            amount_max=Decimal("500.00"),
            description_regex=None,
        )

        assert conditions.description_keywords == ["hotel", "room"]
        assert conditions.vendor_patterns == ["*hotel*"]
        assert conditions.amount_min == Decimal("50.00")
        assert conditions.amount_max == Decimal("500.00")

    def test_amount_range_validation(self):
        """Test that amount_min cannot be greater than amount_max."""
        with pytest.raises(
            ValueError, match="amount_min cannot be greater than amount_max"
        ):
            RuleConditions(
                description_keywords=["test"],
                amount_min=Decimal("100.00"),
                amount_max=Decimal("50.00"),
                description_regex=None,
            )

    def test_decimal_conversion(self):
        """Test that float amounts are converted to Decimal."""
        conditions = RuleConditions(
            description_keywords=["test"],
            amount_min=50.0,
            amount_max=500.0,
            description_regex=None,
        )

        assert isinstance(conditions.amount_min, Decimal)
        assert isinstance(conditions.amount_max, Decimal)
        assert conditions.amount_min == Decimal("50.0")


class TestRuleActions:
    """Tests for RuleActions model."""

    def test_create_rule_actions(self):
        """Test creating rule actions with required fields."""
        actions = RuleActions(
            category="Travel-Lodging",
            deductibility_percentage=100,
            qb_account="Travel - Lodging",
            tax_treatment=TaxTreatment.STANDARD,
            compliance_note=None,
            account_mapping=None,
            business_rule_id=None,
            confidence_boost=0.1,
        )

        assert actions.category == "Travel-Lodging"
        assert actions.deductibility_percentage == 100
        assert actions.qb_account == "Travel - Lodging"
        assert actions.tax_treatment == TaxTreatment.STANDARD
        assert actions.confidence_boost == 0.1

    def test_deductibility_percentage_validation(self):
        """Test that deductibility percentage is validated."""
        with pytest.raises(
            ValidationError, match="Input should be less than or equal to 100"
        ):
            RuleActions(
                category="Test",
                deductibility_percentage=150,  # Invalid: > 100
                qb_account="Test Account",
                compliance_note=None,
                account_mapping=None,
                business_rule_id=None,
            )

        with pytest.raises(
            ValidationError, match="Input should be greater than or equal to 0"
        ):
            RuleActions(
                category="Test",
                deductibility_percentage=-10,  # Invalid: < 0
                qb_account="Test Account",
                compliance_note=None,
                account_mapping=None,
                business_rule_id=None,
            )


class TestBusinessRule:
    """Tests for BusinessRule model and matching logic."""

    @pytest.fixture
    def hotel_rule(self):
        """Create a sample hotel accommodation rule."""
        return BusinessRule(
            id="hotel_accommodation",
            priority=100,
            name="Hotel Accommodation",
            description="Hotel accommodation charges",
            conditions=RuleConditions(
                description_keywords=["room charge", "accommodation"],
                description_patterns=[],
                description_regex=None,
                vendor_patterns=["*hotel*", "*inn*"],
                vendor_keywords=[],
                amount_min=Decimal("30.00"),
                amount_max=Decimal("1000.00"),
                category_hints=[],
            ),
            actions=RuleActions(
                category="Travel-Lodging",
                deductibility_percentage=100,
                qb_account="Travel - Lodging",
                compliance_note=None,
                account_mapping=None,
                business_rule_id=None,
                confidence_boost=0.2,
            ),
        )

    @pytest.fixture
    def meal_rule(self):
        """Create a sample meal rule."""
        return BusinessRule(
            id="restaurant_meals",
            priority=90,
            name="Restaurant Meals",
            description="Restaurant and meal expenses",
            conditions=RuleConditions(
                description_keywords=["restaurant", "meal", "dining"],
                description_patterns=[],
                description_regex=None,
                vendor_patterns=["*restaurant*", "*cafe*"],
                vendor_keywords=[],
                amount_min=None,
                amount_max=None,
                category_hints=[],
            ),
            actions=RuleActions(
                category="Travel-Meals",
                deductibility_percentage=50,
                qb_account="Travel - Meals & Entertainment",
                tax_treatment=TaxTreatment.MEALS_LIMITATION,
                compliance_note=None,
                account_mapping=None,
                business_rule_id=None,
            ),
        )

    def test_matches_description_keywords(self, hotel_rule):
        """Test description keyword matching."""
        assert hotel_rule.matches_description("Room Charge")
        assert hotel_rule.matches_description("Hotel accommodation fee")
        assert not hotel_rule.matches_description("Restaurant meal")

    def test_matches_description_case_insensitive(self, hotel_rule):
        """Test that description matching is case insensitive."""
        assert hotel_rule.matches_description("ROOM CHARGE")
        assert hotel_rule.matches_description("room charge")
        assert hotel_rule.matches_description("Room Charge")

    def test_matches_vendor_patterns(self, hotel_rule):
        """Test vendor pattern matching."""
        assert hotel_rule.matches_vendor("Marriott Hotel")
        assert hotel_rule.matches_vendor("Holiday Inn")
        assert not hotel_rule.matches_vendor("McDonald's Restaurant")

    def test_matches_amount_range(self, hotel_rule):
        """Test amount range matching."""
        assert hotel_rule.matches_amount(Decimal("100.00"))
        assert hotel_rule.matches_amount(Decimal("30.00"))  # Minimum
        assert hotel_rule.matches_amount(Decimal("1000.00"))  # Maximum
        assert not hotel_rule.matches_amount(Decimal("20.00"))  # Below minimum
        assert not hotel_rule.matches_amount(Decimal("1500.00"))  # Above maximum

    def test_matches_all_conditions(self, hotel_rule):
        """Test that all conditions must match."""
        # Matches description and vendor
        assert hotel_rule.matches(
            description="Room Charge",
            vendor_name="Marriott Hotel",
            amount=Decimal("150.00"),
        )

        # Doesn't match description
        assert not hotel_rule.matches(
            description="Restaurant meal",
            vendor_name="Marriott Hotel",
            amount=Decimal("150.00"),
        )

        # Doesn't match amount range
        assert not hotel_rule.matches(
            description="Room Charge",
            vendor_name="Marriott Hotel",
            amount=Decimal("2000.00"),
        )

    def test_disabled_rule_never_matches(self, hotel_rule):
        """Test that disabled rules never match."""
        hotel_rule.enabled = False
        assert not hotel_rule.matches(
            description="Room Charge",
            vendor_name="Marriott Hotel",
            amount=Decimal("150.00"),
        )


class TestBusinessRuleEngine:
    """Tests for BusinessRuleEngine service."""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for testing."""
        return {
            "version": "1.0",
            "rules": [
                {
                    "id": "hotel_accommodation",
                    "priority": 100,
                    "name": "Hotel Accommodation",
                    "conditions": {
                        "description_keywords": ["room charge", "accommodation"],
                        "vendor_patterns": ["*hotel*"],
                        "amount_min": 30.00,
                        "amount_max": 1000.00,
                    },
                    "actions": {
                        "category": "Travel-Lodging",
                        "deductibility_percentage": 100,
                        "qb_account": "Travel - Lodging",
                        "confidence_boost": 0.2,
                    },
                },
                {
                    "id": "restaurant_meals",
                    "priority": 90,
                    "name": "Restaurant Meals",
                    "conditions": {
                        "description_keywords": ["restaurant", "meal"],
                    },
                    "actions": {
                        "category": "Travel-Meals",
                        "deductibility_percentage": 50,
                        "qb_account": "Travel - Meals & Entertainment",
                        "tax_treatment": "meals_limitation",
                    },
                },
            ],
            "fallback_rules": {
                "unknown_expense": {
                    "category": "General Business Expense",
                    "deductibility_percentage": 100,
                    "qb_account": "Other Business Expenses",
                    "tax_treatment": "standard",
                    "requires_manual_review": True,
                }
            },
        }

    @pytest.fixture
    def config_file(self, sample_config):
        """Create a temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_config, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink()

    @pytest.fixture
    def rule_engine(self, config_file):
        """Create a rule engine with test configuration."""
        return BusinessRuleEngine(config_file)

    def test_load_rules_success(self, rule_engine):
        """Test successful rule loading."""
        assert rule_engine.config is not None
        assert len(rule_engine.config.rules) == 2
        assert rule_engine.config.version == "1.0"

    def test_load_rules_file_not_found(self):
        """Test handling of missing config file."""
        with pytest.raises(
            RuleConfigurationError, match="Rule configuration file not found"
        ):
            BusinessRuleEngine("nonexistent.json")

    def test_find_matching_rules(self, rule_engine):
        """Test finding rules that match given criteria."""
        # Should match hotel rule
        matches = rule_engine.find_matching_rules(
            description="Room Charge",
            vendor_name="Marriott Hotel",
            amount=Decimal("150.00"),
        )
        assert len(matches) == 1
        assert matches[0].id == "hotel_accommodation"

        # Should match meal rule
        matches = rule_engine.find_matching_rules(
            description="Restaurant meal",
        )
        assert len(matches) == 1
        assert matches[0].id == "restaurant_meals"

        # Should match no rules
        matches = rule_engine.find_matching_rules(
            description="Unknown expense",
        )
        assert len(matches) == 0

    def test_select_best_rule_by_priority(self, rule_engine):
        """Test selecting best rule based on priority."""
        # Create rules that both match
        rules = rule_engine.config.get_enabled_rules()

        # Hotel rule has higher priority (100 vs 90)
        best_rule = rule_engine.select_best_rule(rules)
        assert best_rule.id == "hotel_accommodation"

        # Test with no rules
        best_rule = rule_engine.select_best_rule([])
        assert best_rule is None

    def test_categorize_line_item_matched_rule(self, rule_engine):
        """Test categorizing a line item that matches a rule."""
        result = rule_engine.categorize_line_item(
            description="Room Charge",
            vendor_name="Marriott Hotel",
            amount=Decimal("150.00"),
        )

        assert result.rule_applied is not None
        assert result.rule_applied.id == "hotel_accommodation"
        assert result.category == "Travel-Lodging"
        assert result.deductibility_percentage == 100
        assert result.qb_account == "Travel - Lodging"
        assert result.confidence_score > 0.8  # Base + boost
        assert not result.is_fallback

    def test_categorize_line_item_fallback(self, rule_engine):
        """Test categorizing a line item that uses fallback rule."""
        result = rule_engine.categorize_line_item(
            description="Unknown expense type",
            amount=Decimal("50.00"),
        )

        assert result.rule_applied is None
        assert result.category == "General Business Expense"
        assert result.deductibility_percentage == 100
        assert result.qb_account == "Other Business Expenses"
        assert result.requires_manual_review
        assert result.is_fallback

    def test_categorize_multiple_line_items(self, rule_engine):
        """Test categorizing multiple line items."""
        line_items = [
            LineItem(description="Room Charge", amount=Decimal("150.00"), quantity=1),
            LineItem(
                description="Restaurant meal", amount=Decimal("35.00"), quantity=1
            ),
            LineItem(
                description="Unknown expense", amount=Decimal("25.00"), quantity=1
            ),
        ]

        context = ExpenseContext(
            vendor_name="Marriott Hotel",
            transaction_date=None,
            total_amount=None,
            payment_method=None,
            business_purpose=None,
            location=None,
        )
        results = rule_engine.categorize_line_items(line_items, context)

        assert len(results) == 3

        # First item: hotel accommodation
        assert results[0].category == "Travel-Lodging"
        assert results[0].deductibility_percentage == 100

        # Second item: restaurant meal
        assert results[1].category == "Travel-Meals"
        assert results[1].deductibility_percentage == 50

        # Third item: fallback
        assert results[2].category == "General Business Expense"
        assert results[2].is_fallback

    def test_rule_application_logging(self, rule_engine):
        """Test that rule applications are logged."""
        initial_count = len(rule_engine.rule_history)

        rule_engine.categorize_line_item(
            description="Room Charge",
            vendor_name="Marriott Hotel",
            amount=Decimal("150.00"),
        )

        assert len(rule_engine.rule_history) == initial_count + 1

        latest_application = rule_engine.rule_history[-1]
        assert latest_application.rule_id == "hotel_accommodation"
        assert latest_application.line_item_description == "Room Charge"
        assert latest_application.vendor_name == "Marriott Hotel"

    def test_get_rule_statistics(self, rule_engine):
        """Test rule usage statistics."""
        # Apply some rules
        rule_engine.categorize_line_item("Room Charge", amount=Decimal("150.00"))
        rule_engine.categorize_line_item("Restaurant meal", amount=Decimal("35.00"))
        rule_engine.categorize_line_item("Unknown expense", amount=Decimal("25.00"))

        stats = rule_engine.get_rule_statistics()

        assert stats["total_applications"] >= 3
        assert "hotel_accommodation" in stats["rule_usage"]
        assert "restaurant_meals" in stats["rule_usage"]
        assert stats["fallback_count"] >= 1
        assert 0 <= stats["average_confidence"] <= 1
        assert stats["unique_rules_used"] >= 2

    def test_validate_configuration(self, rule_engine):
        """Test configuration validation."""
        errors = rule_engine.validate_configuration()

        # Should have no errors for valid configuration
        assert len(errors) == 0

    def test_reload_rules(self, rule_engine, config_file):
        """Test hot-reloading of rules."""
        original_count = len(rule_engine.config.rules)

        # Modify the config file
        with open(config_file) as f:
            config = json.load(f)

        # Add a new rule
        config["rules"].append(
            {
                "id": "new_rule",
                "priority": 50,
                "name": "New Test Rule",
                "conditions": {"description_keywords": ["test"]},
                "actions": {
                    "category": "Test Category",
                    "deductibility_percentage": 100,
                    "qb_account": "Test Account",
                },
            }
        )

        with open(config_file, "w") as f:
            json.dump(config, f)

        # Reload rules
        rule_engine.reload_rules()

        assert len(rule_engine.config.rules) == original_count + 1
        assert rule_engine.config.get_rule_by_id("new_rule") is not None


class TestMarriottHotelBillScenario:
    """Integration tests for Marriott hotel bill processing."""

    @pytest.fixture
    def marriott_line_items(self):
        """Create line items from a Marriott hotel bill."""
        return [
            LineItem(description="Room Charge", amount=Decimal("175.00"), quantity=1),
            LineItem(
                description="Restaurant Room Charge",
                amount=Decimal("40.70"),
                quantity=1,
            ),
            LineItem(description="Marketing Fee", amount=Decimal("5.25"), quantity=1),
            LineItem(description="GST 767657513", amount=Decimal("9.01"), quantity=1),
            LineItem(description="Tourism Levy", amount=Decimal("7.21"), quantity=1),
        ]

    @pytest.fixture
    def marriott_context(self):
        """Create expense context for Marriott hotel."""
        return ExpenseContext(
            vendor_name="Courtyard by Marriott",
            transaction_date=None,
            total_amount=Decimal("237.17"),
            currency="CAD",
            payment_method=None,
            business_purpose=None,
            location=None,
        )

    def test_marriott_bill_categorization(self, marriott_line_items, marriott_context):
        """Test complete Marriott hotel bill categorization."""
        # Use the real configuration
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "business_rules.json"
        )
        if not config_path.exists():
            pytest.skip("Business rules configuration not found")

        engine = BusinessRuleEngine(config_path)
        results = engine.categorize_line_items(marriott_line_items, marriott_context)

        assert len(results) == 5

        # Room Charge: should be Travel-Lodging, 100% deductible
        room_result = results[0]
        assert room_result.category == "Travel-Lodging"
        assert room_result.deductibility_percentage == 100
        assert not room_result.is_fallback

        # Restaurant Room Charge: should be Travel-Meals, 50% deductible
        meal_result = results[1]
        assert meal_result.category == "Travel-Meals"
        assert meal_result.deductibility_percentage == 50
        assert meal_result.tax_treatment == TaxTreatment.MEALS_LIMITATION

        # Marketing Fee: should be Travel-Lodging for hotels (vendor-aware), 100% deductible
        marketing_result = results[2]
        assert marketing_result.category == "Travel-Lodging"
        assert marketing_result.deductibility_percentage == 100

        # GST: should be Tax-GST/HST, 100% deductible, Input Tax Credit
        gst_result = results[3]
        assert gst_result.category == "Tax-GST/HST"
        assert gst_result.deductibility_percentage == 100
        assert gst_result.tax_treatment == TaxTreatment.INPUT_TAX_CREDIT

        # Tourism Levy: should be Travel-Taxes, 100% deductible
        tourism_result = results[4]
        assert tourism_result.category == "Travel-Taxes"
        assert tourism_result.deductibility_percentage == 100

        # Calculate total deductible amount
        total_deductible = sum(
            (item.amount * item.quantity)
            * (Decimal(result.deductibility_percentage) / 100)
            for item, result in zip(marriott_line_items, results, strict=False)
        )

        # Expected: Room(175) + Meal(40.70*0.5) + Marketing(5.25) +
        # GST(9.01) + Tourism(7.21) = 175 + 20.35 + 5.25 + 9.01 + 7.21 = 216.82
        expected_deductible = Decimal("216.82")
        assert abs(total_deductible - expected_deductible) < Decimal("0.01")

    def test_rule_application_audit_trail(self, marriott_line_items, marriott_context):
        """Test that rule applications are properly logged for audit."""
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "business_rules.json"
        )
        if not config_path.exists():
            pytest.skip("Business rules configuration not found")

        engine = BusinessRuleEngine(config_path)
        initial_history_count = len(engine.rule_history)

        engine.categorize_line_items(marriott_line_items, marriott_context)

        # Should have 5 new applications
        assert len(engine.rule_history) == initial_history_count + 5

        # Check specific rule applications
        recent_applications = engine.rule_history[-5:]

        room_app = next(
            app
            for app in recent_applications
            if "Room Charge" in app.line_item_description
        )
        assert room_app.rule_id == "hotel_accommodation"
        assert room_app.vendor_name == "Courtyard by Marriott"

        meal_app = next(
            app
            for app in recent_applications
            if "Restaurant" in app.line_item_description
        )
        assert meal_app.rule_id == "room_service_meals"


class TestVendorAwareBusinessRules:
    """Tests for vendor-aware business rules functionality."""

    def test_hotel_marketing_fee_categorization(self):
        """Test that marketing fees from hotels are categorized as Travel-Lodging."""
        # Create test configuration with hotel marketing fee rule
        config_data = {
            "version": "1.0",
            "metadata": {
                "description": "Test vendor-aware business rules",
                "jurisdiction": "Canada",
            },
            "rules": [
                {
                    "id": "hotel_marketing_fees",
                    "priority": 110,
                    "name": "Hotel Marketing and Service Fees",
                    "description": "Marketing fees from hotels - categorize as lodging",
                    "conditions": {
                        "description_keywords": ["marketing fee"],
                        "vendor_patterns": ["*marriott*", "*hotel*"],
                        "amount_min": 1.0,
                        "amount_max": 100.0,
                    },
                    "actions": {
                        "category": "Travel-Lodging",
                        "deductibility_percentage": 100,
                        "qb_account": "Travel - Lodging",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.2,
                    },
                    "enabled": True,
                },
                {
                    "id": "generic_marketing_fees",
                    "priority": 75,
                    "name": "Marketing and Service Fees (Non-Hotel)",
                    "description": (
                        "Generic marketing fees - categorize as professional services"
                    ),
                    "conditions": {
                        "description_keywords": ["marketing fee"],
                        "amount_min": 1.0,
                        "amount_max": 100.0,
                    },
                    "actions": {
                        "category": "Professional Services",
                        "deductibility_percentage": 100,
                        "qb_account": "Professional Fees",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.02,
                    },
                    "enabled": True,
                },
            ],
            "fallback_rules": {
                "unknown_expense": {
                    "category": "General Business Expense",
                    "deductibility_percentage": 100,
                    "qb_account": "Other Business Expenses",
                    "tax_treatment": "standard",
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            engine = BusinessRuleEngine(config_path)

            # Test hotel marketing fee
            result = engine.categorize_line_item(
                description="Marketing Fee",
                vendor_name="Courtyard by Marriott",
                amount=Decimal("5.25"),
            )

            assert result.category == "Travel-Lodging"
            assert result.qb_account == "Travel - Lodging"
            assert result.rule_applied.id == "hotel_marketing_fees"
            assert result.confidence_score > 0.9  # Should be high confidence

            # Test non-hotel marketing fee
            result = engine.categorize_line_item(
                description="Marketing Fee",
                vendor_name="Generic Company",
                amount=Decimal("5.25"),
            )

            assert result.category == "Professional Services"
            assert result.qb_account == "Professional Fees"
            assert result.rule_applied.id == "generic_marketing_fees"
            assert result.confidence_score < 0.85  # Should be lower confidence

        finally:
            Path(config_path).unlink()

    def test_vendor_context_rule_selection(self):
        """Test that vendor-specific rules are preferred over generic rules."""
        config_data = {
            "version": "1.0",
            "metadata": {"description": "Test vendor context rule selection"},
            "rules": [
                {
                    "id": "vendor_specific_rule",
                    "priority": 80,
                    "name": "Vendor Specific Rule",
                    "description": "Specific rule for certain vendors",
                    "conditions": {
                        "description_keywords": ["service fee"],
                        "vendor_patterns": ["*specific*"],
                    },
                    "actions": {
                        "category": "Vendor-Specific",
                        "deductibility_percentage": 100,
                        "qb_account": "Vendor Specific Account",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.15,
                    },
                    "enabled": True,
                },
                {
                    "id": "generic_rule",
                    "priority": 90,  # Higher priority but no vendor patterns
                    "name": "Generic Rule",
                    "description": "Generic rule for service fees",
                    "conditions": {
                        "description_keywords": ["service fee"],
                    },
                    "actions": {
                        "category": "Generic",
                        "deductibility_percentage": 100,
                        "qb_account": "Generic Account",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.05,
                    },
                    "enabled": True,
                },
            ],
            "fallback_rules": {
                "unknown_expense": {
                    "category": "General Business Expense",
                    "deductibility_percentage": 100,
                    "qb_account": "Other Business Expenses",
                    "tax_treatment": "standard",
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            engine = BusinessRuleEngine(config_path)

            # Test with matching vendor - should select vendor-specific rule
            result = engine.categorize_line_item(
                description="Service Fee",
                vendor_name="Specific Company",
                amount=Decimal("10.00"),
            )

            assert result.category == "Vendor-Specific"
            assert result.rule_applied.id == "vendor_specific_rule"

            # Test with non-matching vendor - should select generic rule
            result = engine.categorize_line_item(
                description="Service Fee",
                vendor_name="Other Company",
                amount=Decimal("10.00"),
            )

            assert result.category == "Generic"
            assert result.rule_applied.id == "generic_rule"

        finally:
            Path(config_path).unlink()

    def test_confidence_scoring_with_vendor_context(self):
        """Test that confidence scores are adjusted based on vendor context."""
        config_data = {
            "version": "1.0",
            "metadata": {"description": "Test confidence scoring"},
            "rules": [
                {
                    "id": "vendor_rule",
                    "priority": 100,
                    "name": "Vendor Specific",
                    "conditions": {
                        "description_keywords": ["fee"],
                        "vendor_patterns": ["*test*"],
                    },
                    "actions": {
                        "category": "Test Category",
                        "deductibility_percentage": 100,
                        "qb_account": "Test Account",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.1,
                    },
                    "enabled": True,
                },
            ],
            "fallback_rules": {
                "unknown_expense": {
                    "category": "General Business Expense",
                    "deductibility_percentage": 100,
                    "qb_account": "Other Business Expenses",
                    "tax_treatment": "standard",
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            engine = BusinessRuleEngine(config_path)

            # Test with matching vendor - should get confidence boost
            result_with_vendor = engine.categorize_line_item(
                description="Test Fee",
                vendor_name="Test Company",
                amount=Decimal("10.00"),
            )

            # Test without vendor context - should have lower confidence
            result_without_vendor = engine.categorize_line_item(
                description="Test Fee",
                vendor_name=None,
                amount=Decimal("10.00"),
            )

            # Vendor context should provide additional confidence
            assert (
                result_with_vendor.confidence_score
                > result_without_vendor.confidence_score
            )

        finally:
            Path(config_path).unlink()

    def test_vendor_category_alignment_validation(self):
        """Test validation of vendor-category alignment."""
        config_data = {
            "version": "1.0",
            "metadata": {"description": "Test vendor alignment validation"},
            "rules": [
                {
                    "id": "misaligned_rule",
                    "priority": 100,
                    "name": "Potentially Misaligned Rule",
                    "conditions": {
                        "description_keywords": ["marketing fee"],
                    },
                    "actions": {
                        "category": "Professional Services",
                        "deductibility_percentage": 100,
                        "qb_account": "Professional Fees",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.1,
                    },
                    "enabled": True,
                },
            ],
            "fallback_rules": {
                "unknown_expense": {
                    "category": "General Business Expense",
                    "deductibility_percentage": 100,
                    "qb_account": "Other Business Expenses",
                    "tax_treatment": "standard",
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            engine = BusinessRuleEngine(config_path)

            # This should trigger a vendor-category alignment warning
            # (hotel vendor with professional services category)
            result = engine.categorize_line_item(
                description="Marketing Fee",
                vendor_name="Marriott Hotel",
                amount=Decimal("5.25"),
            )

            # Rule should still apply, but warning should be logged
            assert result.category == "Professional Services"
            assert result.rule_applied.id == "misaligned_rule"

            # Test the validation method directly
            is_aligned, warning = engine.validate_vendor_category_alignment(
                result.rule_applied, "Marriott Hotel"
            )
            assert not is_aligned
            assert warning is not None
            assert "Hotel vendor" in warning
            assert "consider Travel-Lodging" in warning

        finally:
            Path(config_path).unlink()

    def test_marriott_receipt_scenario(self):
        """Test the specific Marriott receipt scenario from user feedback."""
        # Use the actual business rules configuration
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "business_rules.json"
        )
        engine = BusinessRuleEngine(config_path)

        # Test marketing fee from Marriott
        result = engine.categorize_line_item(
            description="Marketing Fee",
            vendor_name="Courtyard by Marriott",
            amount=Decimal("5.25"),
        )

        # Should now be categorized as Travel-Lodging (fixed!)
        assert result.category == "Travel-Lodging"
        assert result.qb_account == "Travel - Lodging"
        assert result.rule_applied.id == "hotel_marketing_fees"
        assert result.confidence_score > 0.9  # High confidence with vendor context

        # Test that room service meals still work correctly
        result = engine.categorize_line_item(
            description="Restaurant Room Charge",
            vendor_name="Courtyard by Marriott",
            amount=Decimal("40.70"),
        )

        assert result.category == "Travel-Meals"
        assert result.deductibility_percentage == 50
        assert result.rule_applied.id == "room_service_meals"

        # Test room charges
        result = engine.categorize_line_item(
            description="Room Charge",
            vendor_name="Courtyard by Marriott",
            amount=Decimal("175.00"),
        )

        assert result.category == "Travel-Lodging"
        assert result.deductibility_percentage == 100
        assert result.rule_applied.id == "hotel_accommodation"

    def test_multiple_vendor_specific_rules(self):
        """Test scenario with multiple vendor-specific rules matching."""
        config_data = {
            "version": "1.0",
            "metadata": {"description": "Test multiple vendor rules"},
            "rules": [
                {
                    "id": "high_priority_vendor_rule",
                    "priority": 120,
                    "name": "High Priority Vendor Rule",
                    "conditions": {
                        "description_keywords": ["fee"],
                        "vendor_patterns": ["*test*"],
                    },
                    "actions": {
                        "category": "High Priority",
                        "deductibility_percentage": 100,
                        "qb_account": "High Priority Account",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.2,
                    },
                    "enabled": True,
                },
                {
                    "id": "low_priority_vendor_rule",
                    "priority": 100,
                    "name": "Low Priority Vendor Rule",
                    "conditions": {
                        "description_keywords": ["fee"],
                        "vendor_patterns": ["*test*"],
                    },
                    "actions": {
                        "category": "Low Priority",
                        "deductibility_percentage": 100,
                        "qb_account": "Low Priority Account",
                        "tax_treatment": "standard",
                        "confidence_boost": 0.1,
                    },
                    "enabled": True,
                },
            ],
            "fallback_rules": {
                "unknown_expense": {
                    "category": "General Business Expense",
                    "deductibility_percentage": 100,
                    "qb_account": "Other Business Expenses",
                    "tax_treatment": "standard",
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            engine = BusinessRuleEngine(config_path)

            result = engine.categorize_line_item(
                description="Test Fee",
                vendor_name="Test Company",
                amount=Decimal("10.00"),
            )

            # Should select the higher priority rule
            assert result.category == "High Priority"
            assert result.rule_applied.id == "high_priority_vendor_rule"

        finally:
            Path(config_path).unlink()
