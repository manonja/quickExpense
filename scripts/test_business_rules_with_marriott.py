#!/usr/bin/env python3
"""Test business rules with simulated Marriott hotel bill data."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quickexpense.models.business_rules import ExpenseContext
from quickexpense.models.expense import LineItem
from quickexpense.services.business_rules import BusinessRuleEngine


def test_marriott_business_rules():
    """Test business rules with Marriott hotel bill line items."""
    print("🏨 Testing Business Rules with Marriott Hotel Bill")
    print("=" * 60)

    # Initialize business rules engine
    config_path = Path(__file__).parent.parent / "config" / "business_rules.json"
    engine = BusinessRuleEngine(config_path)

    print(f"✅ Loaded {len(engine.config.rules)} business rules")

    # Create simulated Marriott hotel bill line items
    line_items = [
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

    # Create expense context
    context = ExpenseContext(
        vendor_name="Courtyard by Marriott",
        total_amount=Decimal("237.17"),
        currency="CAD",
    )

    print(f"\n🧾 Processing {len(line_items)} line items from: {context.vendor_name}")
    print(f"Total Amount: ${context.total_amount}")

    # Categorize line items
    results = engine.categorize_line_items(line_items, context)

    print("\n📋 Business Rules Categorization Results:")
    print("-" * 60)

    total_deductible = Decimal("0.00")
    for i, (line_item, result) in enumerate(zip(line_items, results, strict=False), 1):
        item_deductible = (line_item.amount * line_item.quantity) * (
            Decimal(result.deductibility_percentage) / 100
        )
        total_deductible += item_deductible

        print(f"\n{i}. {line_item.description}")
        print(f"   Amount: ${line_item.amount * line_item.quantity}")
        print(
            f"   Rule Applied: {result.rule_applied.name if result.rule_applied else 'Fallback Rule'}"
        )
        print(f"   Category: {result.category}")
        print(f"   QuickBooks Account: {result.qb_account}")
        print(
            f"   Tax Deductible: {result.deductibility_percentage}% (${item_deductible})"
        )
        print(f"   Tax Treatment: {result.tax_treatment.value}")
        print(f"   Confidence: {result.confidence_score:.1%}")
        print(f"   {'⚠️  Fallback Rule' if result.is_fallback else '✅ Matched Rule'}")

    # Summary
    print("\n💰 Tax Deductibility Summary:")
    print("-" * 40)
    print(f"Total Amount: ${context.total_amount}")
    print(f"Deductible Amount: ${total_deductible}")
    deductible_percentage = (total_deductible / context.total_amount) * 100
    print(f"Deductible Percentage: {deductible_percentage:.1f}%")

    # Expected vs actual
    expected_deductible = Decimal("216.82")  # From test calculations
    print(f"\nExpected Deductible: ${expected_deductible}")
    print(f"Actual Deductible: ${total_deductible}")
    difference = abs(total_deductible - expected_deductible)
    print(f"Difference: ${difference}")

    if difference < Decimal("0.01"):
        print("✅ Business rules calculation matches expected result!")
    else:
        print("❌ Business rules calculation differs from expected result")

    # Show rule usage statistics
    print("\n📊 Rule Engine Statistics:")
    print("-" * 30)
    stats = engine.get_rule_statistics()
    print(f"Total Applications: {stats['total_applications']}")
    print(f"Unique Rules Used: {stats['unique_rules_used']}")
    print(f"Average Confidence: {stats['average_confidence']:.1%}")
    print(
        f"Fallback Usage: {stats['fallback_count']} ({stats['fallback_percentage']:.1f}%)"
    )

    return results


if __name__ == "__main__":
    test_marriott_business_rules()
