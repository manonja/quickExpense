# Zero Price Line Items Edge Case

## Issue Summary
The CLI fails when processing receipts that contain line items with zero prices (0.0), causing a Pydantic validation error that prevents expense creation.

## Error Details
```
pydantic_core._pydantic_core.ValidationError: 2 validation errors for ExtractedReceipt
line_items.1.unit_price
  Input should be greater than 0 [type=greater_than, input_value=Decimal('0.0'), input_type=Decimal]
line_items.1.total_price
  Input should be greater than 0 [type=greater_than, input_value=Decimal('0.0'), input_type=Decimal]
```

## Root Cause Analysis
1. **Model Constraint**: The `ExtractedReceipt.LineItem` model requires `unit_price` and `total_price` to be greater than 0 (`gt=0`)
2. **AI Extraction**: Gemini extracts ALL visible line items, including those without clear prices
3. **Mismatch**: The prompt instructs "positive numbers" but doesn't explicitly state "greater than zero"

Common scenarios where this occurs:
- Tax or discount line items shown separately
- Complimentary/free items
- Illegible or damaged price information
- Service charges without explicit amounts

## Reproduction Steps
1. Upload a receipt image containing items without prices or zero-priced items
2. Run: `uv run quickexpense upload receipt.jpeg`
3. Observe validation error preventing expense creation

## Proposed Solutions

### Option 1: Filter During Extraction (Recommended)
**Location**: `src/quickexpense/services/gemini.py` after JSON parsing
```python
# Filter out zero-price items and add to notes
valid_items = [item for item in items if item['unit_price'] > 0]
skipped = [item for item in items if item['unit_price'] <= 0]
if skipped:
    notes += f"\nItems without prices: {', '.join(i['description'] for i in skipped)}"
```
**Pros**: Maintains model integrity, preserves information
**Cons**: Requires service-layer changes

### Option 2: Update Prompt Instructions
**Location**: `src/quickexpense/services/gemini.py` in `_build_extraction_prompt()`
```
"2. Only include line items with unit_price and total_price greater than 0"
"3. Items without prices should be mentioned in notes field"
```
**Pros**: Prevents issue at source
**Cons**: Relies on AI compliance, may miss edge cases

### Option 3: Relax Model Validation
**Location**: `src/quickexpense/models/receipt.py`
```python
unit_price: Decimal = Field(..., ge=0)  # Changed from gt=0
```
**Pros**: Accepts all data
**Cons**: Weakens data quality, requires downstream filtering

## Recommendation
Implement **Option 1** with **Option 2** as a complementary measure. This provides both defensive programming and clear AI instructions while maintaining data quality standards.

## Implementation Priority
Low - This is an edge case that doesn't block core functionality for most receipts.
