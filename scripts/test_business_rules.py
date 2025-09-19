#!/usr/bin/env python3
"""Test business rules engine functionality."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quickexpense.models.business_rules import ExpenseContext
from quickexpense.models.expense import LineItem
from quickexpense.services.business_rules import BusinessRuleEngine


def test_business_rules():
    """Test business rules with Marriott hotel bill items."""
    # Load the business rules
    config_path = Path(__file__).parent.parent / "config" / "business_rules.json"

    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return

    print(f"📋 Loading rules from: {config_path}")
    engine = BusinessRuleEngine(config_path)

    print(f"✅ Loaded {len(engine.config.rules)} rules")

    # Test individual line items
    line_items = [
        LineItem(description="Room Charge", amount=Decimal("175.00"), quantity=1),
        LineItem(
            description="Restaurant Room Charge", amount=Decimal("40.70"), quantity=1
        ),
        LineItem(description="Marketing Fee", amount=Decimal("5.25"), quantity=1),
        LineItem(description="GST 767657513", amount=Decimal("9.01"), quantity=1),
        LineItem(description="Tourism Levy", amount=Decimal("7.21"), quantity=1),
    ]

    context = ExpenseContext(
        vendor_name="Courtyard by Marriott",
        total_amount=Decimal("237.17"),
        currency="CAD",
    )

    print("\n🔍 Testing individual line items:")

    for item in line_items:
        print(f"\n📝 Item: {item.description} (${item.amount})")

        # Find matching rules
        matches = engine.find_matching_rules(
            description=item.description,
            vendor_name=context.vendor_name,
            amount=item.amount,
        )

        print(f"   🎯 Found {len(matches)} matching rules:")
        for rule in matches:
            print(f"      - {rule.name} (priority {rule.priority})")

        # Get categorization result
        result = engine.categorize_line_item(
            description=item.description,
            vendor_name=context.vendor_name,
            amount=item.amount,
        )

        print("   📊 Result:")
        print(f"      Category: {result.category}")
        print(f"      Deductible: {result.deductibility_percentage}%")
        print(f"      Account: {result.qb_account}")
        print(f"      Tax Treatment: {result.tax_treatment}")
        print(f"      Confidence: {result.confidence_score:.2f}")
        print(f"      Fallback: {result.is_fallback}")

        if result.rule_applied:
            print(f"      Applied Rule: {result.rule_applied.name}")

    print("\n📈 Rule Usage Statistics:")
    stats = engine.get_rule_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    test_business_rules()
