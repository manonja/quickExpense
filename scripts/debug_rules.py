#!/usr/bin/env python3
"""Debug business rules matching."""

from __future__ import annotations

import fnmatch
import sys
from decimal import Decimal
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quickexpense.services.business_rules import BusinessRuleEngine


def debug_rule_matching():
    """Debug why Room Charge isn't matching."""
    config_path = Path(__file__).parent.parent / "config" / "business_rules.json"
    engine = BusinessRuleEngine(config_path)

    # Get the hotel accommodation rule
    hotel_rule = engine.config.get_rule_by_id("hotel_accommodation")

    print(f"🏨 Hotel Rule: {hotel_rule.name}")
    print(f"   Keywords: {hotel_rule.conditions.description_keywords}")
    print(f"   Vendor patterns: {hotel_rule.conditions.vendor_patterns}")
    print(
        f"   Amount range: {hotel_rule.conditions.amount_min} - {hotel_rule.conditions.amount_max}"
    )

    # Test inputs
    description = "Room Charge"
    vendor_name = "Courtyard by Marriott"
    amount = Decimal("175.00")

    print("\n🔍 Testing:")
    print(f"   Description: '{description}'")
    print(f"   Vendor: '{vendor_name}'")
    print(f"   Amount: ${amount}")

    # Test each condition
    print("\n📝 Description matching:")
    desc_match = hotel_rule.matches_description(description)
    print(f"   Result: {desc_match}")

    for keyword in hotel_rule.conditions.description_keywords:
        match = keyword.lower() in description.lower()
        print(f"   '{keyword}' in '{description}': {match}")

    print("\n🏢 Vendor matching:")
    vendor_match = hotel_rule.matches_vendor(vendor_name)
    print(f"   Result: {vendor_match}")

    for pattern in hotel_rule.conditions.vendor_patterns:
        match = fnmatch.fnmatch(vendor_name.lower(), pattern.lower())
        print(f"   '{vendor_name}' matches '{pattern}': {match}")

    print("\n💰 Amount matching:")
    amount_match = hotel_rule.matches_amount(amount)
    print(f"   Result: {amount_match}")
    print(
        f"   {hotel_rule.conditions.amount_min} <= {amount} <= {hotel_rule.conditions.amount_max}: {amount_match}"
    )

    print("\n🎯 Overall match:")
    overall_match = hotel_rule.matches(description, vendor_name, amount)
    print(f"   Result: {overall_match}")

    # Test room service rule
    print("\n" + "=" * 50)
    room_service_rule = engine.config.get_rule_by_id("room_service_meals")
    print(f"🍽️ Room Service Rule: {room_service_rule.name}")
    print(f"   Keywords: {room_service_rule.conditions.description_keywords}")
    print(f"   Vendor patterns: {room_service_rule.conditions.vendor_patterns}")

    description2 = "Restaurant Room Charge"
    print(f"\n🔍 Testing '{description2}':")

    desc_match2 = room_service_rule.matches_description(description2)
    print(f"   Description match: {desc_match2}")

    for keyword in room_service_rule.conditions.description_keywords:
        match = keyword.lower() in description2.lower()
        print(f"   '{keyword}' in '{description2}': {match}")

    vendor_match2 = room_service_rule.matches_vendor(vendor_name)
    print(f"   Vendor match: {vendor_match2}")

    overall_match2 = room_service_rule.matches(
        description2, vendor_name, Decimal("40.70")
    )
    print(f"   Overall match: {overall_match2}")


if __name__ == "__main__":
    debug_rule_matching()
