# PRE-122 - Fix Local Meal Tax/Tip Processing for CRA Compliance

## Problem Statement

The PHO GEORGIA EXPRESS receipt fails validation with error:
```
Line items total (30.0) does not match expense total (36.23)
```

**Root Cause**: The current business rules engine only processes explicit line items (Shrimp Salad Rolls $11.00 + Lemongrass Pork Sandwich $19.00 = $30.00) but ignores tax ($1.50) and tip ($4.73) amounts extracted by Gemini AI.

**Impact**: Local meal receipts cannot be processed, blocking CRA-compliant expense management for Canadian sole proprietors.

## Receipt Analysis

**PHO GEORGIA EXPRESS Receipt:**
- Line Items: $30.00 (food only)
- GST: $1.50 (5% on $30.00)
- Tip: $4.73
- **Total: $36.23**

**Accountant's Required QuickBooks Format:**
```
Line 1: Meals & Entertainment
Amount: $34.73 (food + tip)
Description: "Business meal - lunch meeting with [Client]"

Line 2: GST/HST Paid on Purchases
Amount: $1.50
Description: "GST - Input Tax Credit"

Total: $36.23
```

## Acceptance Criteria

### ✅ Core Functionality
- [ ] PHO receipt processes successfully without validation errors
- [ ] Creates exactly 2 categorized line items totaling $36.23
- [ ] Line 1: Meals & Entertainment = $34.73 (food + tip combined)
- [ ] Line 2: GST/HST Paid on Purchases = $1.50 (separate for input tax credit)
- [ ] MultiCategoryExpense validation passes

### ✅ Tax Compliance
- [ ] Meals & Entertainment category has 50% deductibility
- [ ] GST category has 100% deductibility (input tax credit)
- [ ] Business purpose documentation required for local meals
- [ ] CRA compliance maintained per accountant specifications

### ✅ Backward Compatibility
- [ ] Marriott travel expense processing unchanged
- [ ] Existing multi-category business rules preserved
- [ ] GST line items remain separate in travel receipts
- [ ] All current tests continue passing

### ✅ User Experience
- [ ] Clear error messages if business purpose missing
- [ ] CLI prompting for local meal business context
- [ ] Dry-run mode shows correct 2-line categorization
- [ ] JSON output format includes proper line item breakdown

## Technical Implementation Plan

### Phase 1: Core Logic Fix

#### 1.1 Modify Business Rules Processing (`src/quickexpense/cli.py`)

**Current Issue**: `_apply_business_rules()` only processes explicit line items from Gemini extraction.

**Solution**: Enhanced logic to handle tax/tip allocation:

```python
def _apply_business_rules(self, receipt_data: Any) -> tuple[...]:
    # Existing line item processing
    rule_results = self.business_rules_engine.apply_rules(...)

    # NEW: Check if we have unallocated amounts
    line_items_total = sum(item amounts from rule_results)
    receipt_total = receipt_data.total_amount
    tax_amount = getattr(receipt_data, 'tax_amount', 0)
    tip_amount = getattr(receipt_data, 'tip_amount', 0)

    # NEW: For local meals, combine food+tip, keep GST separate
    if is_local_meal(receipt_data):
        categorized_items = self._process_local_meal(
            rule_results, tax_amount, tip_amount
        )
    else:
        # Existing travel/multi-category logic
        categorized_items = self._process_existing_logic(rule_results)
```

#### 1.2 Add Local Meal Detection

```python
def is_local_meal(self, receipt_data: Any) -> bool:
    """Detect if receipt is local meal vs travel meal."""
    # Simple heuristic: no travel-related line items
    line_items = getattr(receipt_data, 'line_items', [])
    travel_keywords = ['room', 'hotel', 'lodging', 'accommodation']

    return not any(
        keyword in item.description.lower()
        for item in line_items
        for keyword in travel_keywords
    )
```

#### 1.3 Local Meal Processing Logic

```python
def _process_local_meal(
    self,
    rule_results: list,
    tax_amount: Decimal,
    tip_amount: Decimal
) -> list[CategorizedLineItem]:
    """Process local meal with food+tip combined, GST separate."""

    # Combine all food items + tip into single meal category
    food_items = [r for r in rule_results if 'meal' in r.category.lower()]
    total_food = sum(item.amount for item in food_items)

    meal_item = CategorizedLineItem(
        description=f"Business meal - {', '.join(item.description for item in food_items)}",
        amount=total_food + tip_amount,  # Food + tip combined
        category="Meals & Entertainment",
        deductibility_percentage=50,
        account_mapping="Travel - Meals & Entertainment",
        tax_treatment="meals_limitation"
    )

    # Create separate GST line item if tax_amount > 0
    items = [meal_item]
    if tax_amount > 0:
        gst_item = CategorizedLineItem(
            description="GST - Input Tax Credit",
            amount=tax_amount,
            category="Tax-GST/HST",
            deductibility_percentage=100,
            account_mapping="GST/HST Paid on Purchases",
            tax_treatment="input_tax_credit"
        )
        items.append(gst_item)

    return items
```

### Phase 2: Business Context Integration

#### 2.1 Add CLI Business Purpose Flag
```bash
uv run quickexpense upload receipt.jpg --purpose "client meeting"
uv run quickexpense upload receipt.jpg --purpose "working lunch"
```

#### 2.2 Interactive Prompting for Local Meals
```python
def prompt_business_purpose(self, vendor_name: str) -> str:
    """Prompt user for business purpose for local meals."""
    print(f"\n🍽️ Local meal detected: {vendor_name}")
    print("CRA requires business purpose documentation.")

    purpose = input("Business purpose (e.g., 'client meeting with John re: Project X'): ")
    if not purpose.strip():
        raise ValueError("Business purpose required for meal deduction")

    return purpose.strip()
```

### Phase 3: Testing & Validation

#### 3.1 Test Cases
1. **PHO Receipt Success**: 2-line format, validation passes
2. **Marriott Compatibility**: Existing multi-category preserved
3. **Edge Cases**: No tip, no tax, mixed receipts
4. **Business Purpose**: Prompting and validation

#### 3.2 Regression Testing
- All existing tests pass
- Travel expense processing unchanged
- CLI output format preserved

## File Changes Required

### Primary Changes
- `src/quickexpense/cli.py` - Business rules processing logic
- `src/quickexpense/models/enhanced_expense.py` - Validation updates (if needed)

### Secondary Changes
- `config/business_rules.json` - Add local meal rules (if needed)
- `tests/` - Add test cases for local meal processing

### Documentation Updates
- Update CLI help text for `--purpose` flag
- Add examples in CLAUDE.md

## Testing Strategy

### Unit Tests
```python
def test_pho_receipt_processing():
    """Test PHO receipt creates correct 2-line format."""
    # Given: PHO receipt data with food $30, tax $1.50, tip $4.73
    # When: Process through business rules
    # Then: Creates 2 line items totaling $36.23

def test_local_meal_detection():
    """Test detection of local vs travel meals."""
    # Given: Various receipt types
    # When: Check is_local_meal()
    # Then: Correctly identifies local restaurant vs hotel
```

### Integration Tests
```python
def test_cli_pho_receipt_end_to_end():
    """Test complete CLI processing of PHO receipt."""
    # Given: Actual PHO receipt file
    # When: Run CLI upload command
    # Then: No validation errors, correct categorization
```

### Manual Testing
1. Process PHO receipt with `--dry-run`
2. Verify Marriott receipt still works
3. Test business purpose prompting
4. Check JSON output format

## Risk Assessment

### Low Risk
- Isolated changes to business rules processing
- Backward compatibility maintained
- Clear acceptance criteria

### Mitigation Strategies
- Feature branch isolation
- Comprehensive test coverage
- Manual verification with both receipt types
- Rollback plan if issues arise

## Definition of Done

- [ ] All acceptance criteria met
- [ ] PHO receipt processes successfully
- [ ] Marriott compatibility verified
- [ ] Unit and integration tests pass
- [ ] Manual testing completed
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] Feature merged to main branch

## Success Metrics

**Before**: PHO receipt fails validation with line item mismatch error
**After**: PHO receipt processes successfully with accountant's 2-line QuickBooks format

**Quantifiable**: 100% of local meal receipts process without validation errors while maintaining backward compatibility with travel expenses.
