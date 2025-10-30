# GST Line Item Fix Plan

## Problem
IMG_7597.HEIC shows $15.00 deductible instead of $18.87 because GST line item is missing.

**Current:** 2 meal items @ 50% = $15.00
**Expected:** 2 meals @ 50% + GST $1.50 @ 100% = $16.50 (or $18.87 with tip)

## Root Cause
CRArulesAgent only processes items in `line_items` array. DataExtractionAgent extracts `tax_amount: 1.50` as top-level field, but CRArulesAgent never sees it.

## Solution (80/20 - Minimal Fix)
Add pre-processing in CRArulesAgent to create GST line item from `tax_amount` field before LLM processing.

## Implementation

### Single Change: `src/quickexpense/services/agents/cra_rules_agent.py`

Add helper method:
```python
def _add_tax_and_tip_items(self, line_items: list, receipt_data: dict) -> list:
    """Add tax/tip as line items if present."""
    items = line_items.copy()

    # Add GST if present
    tax_amount = receipt_data.get("tax_amount", 0)
    if tax_amount and tax_amount > 0:
        # Check if not already in items
        has_tax = any("gst" in str(item.get("description", "")).lower() or
                      "tax" in str(item.get("description", "")).lower()
                      for item in items)
        if not has_tax:
            items.append({
                "description": "GST/HST",
                "total_price": float(tax_amount),
                "quantity": 1,
                "unit_price": float(tax_amount)
            })

    # Add tip if present (optional - can skip for 80/20)
    tip_amount = receipt_data.get("tip_amount", 0)
    if tip_amount and tip_amount > 0:
        has_tip = any("tip" in str(item.get("description", "")).lower()
                      for item in items)
        if not has_tip:
            items.append({
                "description": "Tip",
                "total_price": float(tip_amount),
                "quantity": 1,
                "unit_price": float(tip_amount)
            })

    return items
```

Call it in `_build_refinement_prompt()` (line ~245):
```python
# Before building line_items_json:
line_items = self._add_tax_and_tip_items(line_items, receipt_data)
```

Call it in `_build_fallback_prompt()` (line ~307):
```python
# Before building line_items_json:
line_items = self._add_tax_and_tip_items(line_items, receipt_data)
```

## Testing
1. Re-run IMG_7597.HEIC → should show ~$18.87 deductible
2. Quick check marriot.pdf still works

## Done
That's it. No orchestrator changes, no new files, no complex logic. Just add missing line items before LLM sees them.
