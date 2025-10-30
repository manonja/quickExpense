#!/usr/bin/env python
"""Test agents API with real receipts using RAG context."""

import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, "src")

# Initialize RAG database
import qe_tax_rag as qe

qe.init()
print("✅ RAG database initialized\n")

# Import after RAG initialization
from quickexpense.core.config import get_settings  # noqa: E402
from quickexpense.services.agents import (  # noqa: E402
    AgentOrchestrator,
    CRArulesAgent,
    DataExtractionAgent,
)


async def test_receipt(receipt_path: str, context: str = "Business expense") -> None: # noqa: PLR0915
    """Test a single receipt with agents + RAG."""
    path = Path(receipt_path)
    if not path.exists():
        print(f"❌ File not found: {receipt_path}")
        return

    # Load and encode file
    with open(path, "rb") as f:  # noqa: ASYNC230
        file_data = f.read()
    file_base64 = base64.b64encode(file_data).decode("utf-8")

    print(f"📄 Receipt: {path.name}")
    print(f"📝 Context: {context}")
    print(f"📊 Size: {len(file_data) / 1024:.1f} KB\n")

    # Process with agents
    settings = get_settings()

    # Initialize agents with longer timeouts
    data_extraction_agent = DataExtractionAgent(settings=settings, timeout_seconds=30.0)
    cra_rules_agent = CRArulesAgent(settings=settings, timeout_seconds=30.0)

    # Create orchestrator
    orchestrator = AgentOrchestrator(
        data_extraction_agent=data_extraction_agent,
        cra_rules_agent=cra_rules_agent,
        consensus_threshold=0.75,
    )

    print("🤖 Processing with agents + RAG...\n")
    result = await orchestrator.process_receipt(
        file_base64=file_base64,
        additional_context=context,
    )

    # Display results
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Success: {result.success}")
    print(f"Overall Confidence: {result.overall_confidence:.2%}")
    print(f"Processing Time: {result.processing_time:.2f}s")
    print(f"Consensus: {result.consensus_method}\n")

    # Agent results
    print("🤖 AGENTS")
    for agent in result.agent_results:
        status = "✅" if agent.success else "❌"
        print(
            f"{status} {agent.agent_name}: {agent.confidence_score:.2%} ({agent.processing_time:.2f}s)"
        )
    print()

    # Expense details
    data = result.final_data
    print("📋 EXPENSE")
    print(f"Vendor: {data.get('vendor_name')}")
    print(f"Date: {data.get('transaction_date')}")

    # Convert amounts to float for display (defensive)
    total_amt = float(data.get("total_amount", 0)) if data.get("total_amount") else 0.0
    tax_amt = float(data.get("tax_amount", 0)) if data.get("tax_amount") else 0.0

    print(f"Total: ${total_amt:.2f}")
    print(f"Tax: ${tax_amt:.2f}\n")

    # CRA categorization
    print("🇨🇦 CRA ANALYSIS")
    print(f"Category: {data.get('category')}")
    print(f"QB Account: {data.get('qb_account')}")
    print(f"Deductibility: {data.get('deductibility_percentage')}%")

    deduct_amt = (
        float(data.get("deductible_amount", 0))
        if data.get("deductible_amount")
        else 0.0
    )
    print(f"Deductible: ${deduct_amt:.2f}")
    print(f"ITA Section: {data.get('ita_section')}")
    print(f"Audit Risk: {data.get('audit_risk')}\n")

    # Line items
    items = data.get("line_items", [])
    if items:
        print(f"📝 LINE ITEMS ({len(items)})")
        for i, item in enumerate(items[:5], 1):
            item_amt = float(item.get("amount", 0)) if item.get("amount") else 0.0
            print(f"{i}. {item.get('description')}: ${item_amt:.2f}")
            print(
                f"   → {item.get('category')} ({item.get('deductibility_percentage')}%)"
            )
        if len(items) > 5:
            print(f"   ... and {len(items) - 5} more")
        print()

    # Flags
    if result.flags_for_review:
        print("⚠️  FLAGS")
        for flag in result.flags_for_review:
            print(f"  - {flag}")
        print()

    print("=" * 70)
    print()


async def main() -> None:
    """Main test runner."""
    receipts_dir = Path("/Users/manonjacquin/Documents/receipts")

    # Test cases with real receipts
    tests = [
        ("Harrods.jpg", "Shopping at luxury department store"),
        ("marriot.pdf", "Hotel accommodation for business conference"),
        ("marriot.png", "Hotel invoice for business trip"),
        ("IMG_7597.HEIC", "Business expense - HEIC photo"),
        ("IMG_7598.HEIC", "Business expense - HEIC photo"),
        ("15-Sep-2025.jpeg", "Business expense receipt"),
    ]

    if len(sys.argv) > 1:
        # Single receipt test
        receipt = sys.argv[1]
        context = sys.argv[2] if len(sys.argv) > 2 else "Business expense"
        await test_receipt(receipt, context)
    else:
        # Test all available receipts
        print("🧪 Testing with real receipts from Documents/receipts\n")

        for filename, context in tests:
            receipt_path = receipts_dir / filename
            if receipt_path.exists():
                await test_receipt(str(receipt_path), context)
                print("\n" + "=" * 70 + "\n")
            else:
                print(f"⏭️  Skipping {filename} (not found)\n")


if __name__ == "__main__":
    asyncio.run(main())
