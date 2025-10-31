# UI Agent Data Display Fix - Implementation Plan

**Created**: 2025-10-31
**Status**: READY FOR IMPLEMENTATION
**Priority**: HIGH
**Complexity**: MEDIUM

---

## Executive Summary

**Problem**: Agent processing works correctly on backend (100% citation rate from PR #23), but UI displays "$0.00 deductible", "0.0% rate", and "No business rules applied" instead of showing the actual processed data.

**Root Cause**: Data structure mismatch between orchestrator output (new line-item fields) and API endpoint field mappings (expecting old aggregated fields).

**Solution**: Update `web_endpoints.py` to correctly map the new orchestrator fields and transform line-item data for UI consumption.

**Impact**:
- Users will see correct tax deductibility calculations
- Line-item processing from PR #23 will be visible
- Citations will be accessible in the UI
- Agent system will appear functional (not broken)

---

## Goals

### Primary Goals
1. **Fix data display**: Show correct deductible amounts and rates on UI
2. **Display line items**: Show individual processed items instead of generic "no rules applied"
3. **Expose citations**: Make RAG citations available for UI rendering
4. **Maintain compatibility**: Ensure non-agent endpoint continues working

### Secondary Goals
1. **Enable debugging**: Provide clear agent processing details
2. **Support future enhancements**: Structure data for citation display in UI
3. **Improve user trust**: Show transparent multi-agent processing results

---

## Problem Analysis

### Data Flow Breakdown

```
┌─────────────────────────────────────────────────────────────────────┐
│ BACKEND: orchestrator.py (process_receipt)                          │
│                                                                      │
│ Output Structure (lines 213-220):                                   │
│   final_data = {                                                    │
│     "line_items": [                        ← NEW (PR #23)          │
│       {                                                             │
│         "line_number": 1,                                           │
│         "original_description": "Pho",                              │
│         "category": "Meals & Entertainment",                        │
│         "original_amount": 34.73,                                   │
│         "deductible_amount": 17.37,                                 │
│         "deductibility_percent": 50,                                │
│         "citations": ["T4002-P46-a73c204c", ...]  ← NEW (PR #23)  │
│       }                                                             │
│     ],                                                              │
│     "total_amount": 36.23,                                          │
│     "total_deductible": 18.87,             ← NEW (PR #23)          │
│     "deductibility_rate": 52.1              ← NEW (PR #23)          │
│   }                                                                 │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│ API ENDPOINT: web_endpoints.py (upload_receipt_with_agents)         │
│                                                                      │
│ Current Code (lines 694-702) - BROKEN:                              │
│   agent_response = MultiAgentReceiptResponse(                       │
│     deductibility_percentage=final_data.get("deductibility_percentage"), │
│     deductible_amount=final_data.get("deductible_amount"),          │
│   )                                                                 │
│                                                                      │
│ Problem: These fields don't exist in final_data!                    │
│   - final_data has: "deductibility_rate" (not "deductibility_percentage") │
│   - final_data has: "total_deductible" (not "deductible_amount")    │
│   - Result: agent_response.deductible_amount = None                 │
│             agent_response.deductibility_percentage = None          │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│ API RESPONSE: tax_deductibility (lines 792-799)                     │
│                                                                      │
│   "tax_deductibility": {                                            │
│     "deductible_amount": f"{float(None or 0):.2f}",  → "$0.00"     │
│     "deductibility_rate": f"{float(None or 0):.1f}"  → "0.0%"      │
│   }                                                                 │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│ UI: app.js (populateTaxBasic, populateBusinessRulesBasic)           │
│                                                                      │
│ Displays:                                                           │
│   - Deductible: $0.00          ← WRONG                             │
│   - Rate: 0.0%                  ← WRONG                             │
│   - "No business rules applied" ← WRONG                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Evidence from Test Case

**Receipt**: IMG_7597.HEIC (Pho Georgia Express, $30.00 CAD)

**Expected Output** (from backend logs):
- Line 1: Meals & Entertainment, $28.50 × 50% = $14.25
- Line 2: GST, $1.50 × 100% = $1.50
- Total Deductible: $15.75
- Rate: 52.5%

**Actual UI Output**:
- Deductible: $0.00
- Rate: 0.0%
- Business Rules: "No business rules applied"

---

## Solution Design

### Architecture Changes

```
┌─────────────────────────────────────────────────────────────────────┐
│ SOLUTION COMPONENTS                                                  │
│                                                                      │
│ 1. Fix Field Mappings (web_endpoints.py lines 696, 702)             │
│    - Map: "total_deductible" → agent_response.deductible_amount     │
│    - Map: "deductibility_rate" → agent_response.deductibility_percentage │
│                                                                      │
│ 2. Transform Line Items to Business Rules (lines 768-790)           │
│    - Convert: final_data["line_items"] → business_rules["applied_rules"] │
│    - Display each line item as a rule with category, amount, %      │
│                                                                      │
│ 3. Expose Citations (line 867)                                      │
│    - Include: line_items with citations in agent_details            │
│    - Enable future UI citation rendering                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Code Changes Required

#### Change 1: Fix MultiAgentReceiptResponse Field Mapping

**File**: `src/quickexpense/api/web_endpoints.py`
**Location**: Lines 694-702

**Current Code**:
```python
agent_response = MultiAgentReceiptResponse(
    success=consensus_result.success,
    overall_confidence=consensus_result.overall_confidence,
    # Receipt data
    vendor_name=final_data.get("vendor_name"),
    transaction_date=final_data.get("transaction_date"),
    total_amount=final_data.get("total_amount"),
    subtotal=final_data.get("subtotal"),
    tax_amount=final_data.get("tax_amount"),
    # CRA categorization
    category=final_data.get("category"),
    deductibility_percentage=final_data.get("deductibility_percentage"),  # ← WRONG
    qb_account=final_data.get("qb_account"),
    ita_section=final_data.get("ita_section"),
    audit_risk=final_data.get("audit_risk"),
    # Tax calculations
    calculated_gst_hst=final_data.get("calculated_gst_hst"),
    deductible_amount=final_data.get("deductible_amount"),  # ← WRONG
    tax_validation_result=final_data.get("tax_validation_result"),
    # ... rest
)
```

**Fixed Code**:
```python
agent_response = MultiAgentReceiptResponse(
    success=consensus_result.success,
    overall_confidence=consensus_result.overall_confidence,
    # Receipt data
    vendor_name=final_data.get("vendor_name"),
    transaction_date=final_data.get("transaction_date"),
    total_amount=final_data.get("total_amount"),
    subtotal=final_data.get("subtotal"),
    tax_amount=final_data.get("tax_amount"),
    # CRA categorization (use first line item for backward compatibility)
    category=final_data.get("line_items", [{}])[0].get("category") if final_data.get("line_items") else final_data.get("category"),
    deductibility_percentage=final_data.get("deductibility_rate"),  # ← FIXED: Use new field
    qb_account=final_data.get("qb_account"),
    ita_section=final_data.get("ita_section"),
    audit_risk=final_data.get("audit_risk"),
    # Tax calculations (use new aggregated fields from orchestrator)
    calculated_gst_hst=final_data.get("calculated_gst_hst"),
    deductible_amount=final_data.get("total_deductible"),  # ← FIXED: Use new field
    tax_validation_result=final_data.get("tax_validation_result"),
    # ... rest
)
```

#### Change 2: Add Line Items Transformation Helper

**File**: `src/quickexpense/api/web_endpoints.py`
**Location**: Add before line 598 (before `upload_receipt_with_agents` function)

**New Helper Function**:
```python
def _format_line_items_as_rules(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert orchestrator line_items to business rules format for UI display.

    Args:
        line_items: Processed line items from orchestrator with citations

    Returns:
        List of rule dictionaries compatible with UI expectations
    """
    if not line_items:
        return []

    rules = []
    for item in line_items:
        rule = {
            "description": item.get("original_description", f"Line {item.get('line_number', '?')}"),
            "rule_name": "CRArulesAgent Line-Item Processing",
            "rule_applied": "agent_line_item_categorization",
            "category": item.get("category", "Uncategorized"),
            "qb_account": item.get("qb_account", "Unknown"),  # May not be in current structure
            "amount": float(item.get("original_amount", 0)),
            "deductible_percentage": item.get("deductibility_percent", 0),
            "tax_treatment": "CRA rules applied",
            "confidence": 0.7,  # Placeholder - not in current line_item structure
            # Include citations for future UI rendering
            "citations": item.get("citations", []),
        }
        rules.append(rule)

    return rules
```

#### Change 3: Update Business Rules Structure

**File**: `src/quickexpense/api/web_endpoints.py`
**Location**: Lines 768-790

**Current Code**:
```python
"business_rules": {
    "applied_rules": (
        [
            {
                "description": (
                    f"Agent consensus: {agent_response.category}"
                ),
                "rule_name": "Multi-Agent Analysis",
                "rule_applied": "agent_consensus",
                "category": agent_response.category,
                "qb_account": agent_response.qb_account,
                "amount": float(agent_response.total_amount or 0),
                "deductible_percentage": (
                    agent_response.deductibility_percentage
                ),
                "tax_treatment": agent_response.tax_validation_result,
                "confidence": agent_response.overall_confidence,
            }
        ]
        if agent_response.category
        else []
    ),
    "total_categories": 1 if agent_response.category else 0,
},
```

**Fixed Code**:
```python
"business_rules": {
    "applied_rules": _format_line_items_as_rules(
        final_data.get("line_items", [])
    ),
    "total_categories": len(final_data.get("line_items", [])),
},
```

#### Change 4: Expose Line Items with Citations in Agent Details

**File**: `src/quickexpense/api/web_endpoints.py`
**Location**: Line 867 (inside `agent_details` dictionary)

**Current Code**:
```python
"agent_details": {
    "overall_confidence": agent_response.overall_confidence,
    "consensus_method": agent_response.consensus_method,
    "flags_for_review": agent_response.flags_for_review,
    "agent_results": [...],
    "agent_breakdown": {...},
    "full_agent_data": agent_response.full_data,
},
```

**Enhanced Code**:
```python
"agent_details": {
    "overall_confidence": agent_response.overall_confidence,
    "consensus_method": agent_response.consensus_method,
    "flags_for_review": agent_response.flags_for_review,
    "agent_results": [...],
    "agent_breakdown": {...},
    "full_agent_data": {
        **agent_response.full_data,
        # Explicitly include line items with citations for UI access
        "line_items": final_data.get("line_items", []),
    },
},
```

---

## User Flow

### Current Broken Flow

```
1. User uploads IMG_7597.HEIC via web UI
2. User enables "Agent Mode" checkbox
3. User clicks "Upload"
4. Backend processes correctly:
   - DataExtractionAgent: Extracts 2 line items
   - CRArulesAgent: Categories + calculates deductibility
   - Orchestrator: Aggregates to total_deductible = $18.87
5. API returns response with deductible_amount = None
6. UI displays:
   ❌ Deductible: $0.00
   ❌ Rate: 0.0%
   ❌ "No business rules applied"
7. User thinks: "Agent system is broken"
```

### Fixed Flow

```
1. User uploads IMG_7597.HEIC via web UI
2. User enables "Agent Mode" checkbox
3. User clicks "Upload"
4. Backend processes correctly:
   - DataExtractionAgent: Extracts 2 line items
   - CRArulesAgent: Categories + calculates deductibility
   - Orchestrator: Aggregates to total_deductible = $18.87
5. API correctly maps fields:
   - total_deductible → agent_response.deductible_amount
   - deductibility_rate → agent_response.deductibility_percentage
   - line_items → business_rules.applied_rules
6. UI displays:
   ✅ Deductible: $18.87
   ✅ Rate: 52.1%
   ✅ Business Rules Applied:
      - "Pho" → Meals & Entertainment (50% deductible, $17.37)
      - "GST" → Tax-GST/HST (100% deductible, $1.50)
7. User thinks: "Agent system works perfectly!"
```

---

## Acceptance Criteria

### Must-Have (Blocking)

- [ ] **AC1**: UI displays correct deductible amount (not $0.00)
  - **Test**: Upload IMG_7597.HEIC with agent mode
  - **Expected**: Deductible shows $18.87 (or similar non-zero amount)

- [ ] **AC2**: UI displays correct deductibility rate percentage (not 0.0%)
  - **Test**: Upload IMG_7597.HEIC with agent mode
  - **Expected**: Rate shows ~52.1% (or similar non-zero rate)

- [ ] **AC3**: UI shows "Agent Processing" mode indicator
  - **Test**: Upload any receipt with agent mode enabled
  - **Expected**: "Mode: Agent Processing (2-Agent System)" visible

- [ ] **AC4**: Business rules section shows individual line items
  - **Test**: Upload IMG_7597.HEIC with agent mode
  - **Expected**: Shows 2+ line items (meals, GST) instead of "No business rules applied"

- [ ] **AC5**: Each line item displays category name
  - **Test**: Upload IMG_7597.HEIC with agent mode
  - **Expected**: Categories like "Meals & Entertainment", "Tax-GST/HST" visible

- [ ] **AC6**: Each line item displays deductibility percentage
  - **Test**: Upload IMG_7597.HEIC with agent mode
  - **Expected**: Shows "50%" for meals, "100%" for GST

- [ ] **AC7**: No regression on non-agent endpoint
  - **Test**: Upload receipt with agent mode DISABLED
  - **Expected**: Still works correctly with Gemini + business rules

### Should-Have (Important)

- [ ] **AC8**: Citations available in agent_details.full_agent_data
  - **Test**: Check API response JSON structure
  - **Expected**: `agent_details.full_agent_data.line_items[].citations` contains citation IDs

- [ ] **AC9**: Line items show original amounts
  - **Test**: Upload IMG_7597.HEIC with agent mode
  - **Expected**: Shows $28.50 for meals, $1.50 for GST (original amounts)

- [ ] **AC10**: Processing summary shows correct item count
  - **Test**: Upload multi-item receipt
  - **Expected**: "Items Processed: 4" matches actual line_items count

### Nice-to-Have (Future)

- [ ] **AC11**: UI displays citations (requires UI enhancement)
  - **Test**: Upload receipt, expand details
  - **Expected**: Shows citation IDs like "T4002-P46-a73c204c"

- [ ] **AC12**: Citations are clickable links to CRA sources
  - **Test**: Click citation ID
  - **Expected**: Opens CRA document in new tab

---

## Testing Strategy

### Unit Testing

**Not Required** - These are data transformation changes without complex logic.

### Integration Testing

#### Test 1: Agent Mode End-to-End (Critical Path)

**Setup**:
1. Start server: `uv run fastapi dev src/quickexpense/main.py`
2. Open browser: `http://localhost:8000`
3. Authenticate with QuickBooks (if not already)

**Test Case 1.1: Pho Georgia Express Receipt**
```bash
# Test file
Receipt: /Users/manonjacquin/Documents/receipts/IMG_7597.HEIC
Vendor: PHO GEORGIA EXPRESS
Expected items: 2-4 line items

Steps:
1. Enable "Agent Mode" checkbox
2. Enable "Dry Run" checkbox (to avoid QuickBooks creation)
3. Upload IMG_7597.HEIC
4. Wait for processing (30-60 seconds)

Expected Results:
✅ Receipt Info:
   - Vendor: PHO GEORGIA EXPRESS
   - Date: 2025-09-24
   - Total: $30.00 CAD

✅ Tax Deductibility:
   - Total Amount: $30.00
   - Deductible: $15.00-$20.00 (NOT $0.00)
   - Rate: 50-70% (NOT 0.0%)

✅ Business Rules Applied:
   - Mode: Agent Processing (2-Agent System)
   - Shows 2+ line items (NOT "No business rules applied")
   - Line 1: Meals/Food category, 50% deductible
   - Line 2: GST/Tax category, 100% deductible

✅ Processing Summary:
   - Overall Confidence: 70-100%
   - DataExtractionAgent: Success
   - CRArulesAgent: Success
```

**Test Case 1.2: Marriott Hotel Receipt**
```bash
# Test file
Receipt: /Users/manonjacquin/Documents/receipts/marriot.pdf
Expected items: 8-12 line items

Steps:
1. Enable "Agent Mode" checkbox
2. Enable "Dry Run" checkbox
3. Upload marriot.pdf
4. Wait for processing (60-90 seconds)

Expected Results:
✅ Tax Deductibility:
   - Deductible: >$0.00 (should show partial deductibility)
   - Rate: >0.0% (likely 50-100%)

✅ Business Rules Applied:
   - Shows 8+ line items (room charge, meals, fees, etc.)
   - Different categories per item
   - Different deductibility percentages
```

**Test Case 1.3: Harrods Receipt**
```bash
# Test file
Receipt: /Users/manonjacquin/Documents/receipts/Harrods.jpg
Expected: Retail items (may be uncategorized)

Steps:
1. Enable "Agent Mode" checkbox
2. Enable "Dry Run" checkbox
3. Upload Harrods.jpg
4. Wait for processing

Expected Results:
✅ Shows line items (even if "Uncategorized-Review-Required")
✅ Citations present (3 citations per test documentation)
✅ No crashes or errors
```

#### Test 2: Non-Agent Mode Regression Test

**Test Case 2.1: Standard Processing Still Works**
```bash
Steps:
1. DISABLE "Agent Mode" checkbox (uncheck it)
2. Enable "Dry Run" checkbox
3. Upload IMG_7597.HEIC
4. Wait for processing (10-20 seconds, faster than agent mode)

Expected Results:
✅ Receipt processed successfully
✅ Shows deductible amount (uses Gemini + business rules)
✅ Shows business rules applied
✅ No errors or crashes
```

#### Test 3: API Response Validation

**Test Case 3.1: Verify Response Structure**
```bash
# Use curl to inspect raw API response
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@/Users/manonjacquin/Documents/receipts/IMG_7597.HEIC" \
  -F "dry_run=true" \
  -F "additional_context=Business expense" \
  | jq '.' > /tmp/agent_response.json

# Validate response structure
cat /tmp/agent_response.json | jq '{
  deductible: .tax_deductibility.deductible_amount,
  rate: .tax_deductibility.deductibility_rate,
  line_items_count: (.business_rules.applied_rules | length),
  first_item: .business_rules.applied_rules[0],
  citations_available: (.agent_details.full_agent_data.line_items[0].citations | length)
}'

Expected Output:
{
  "deductible": "18.87",           # NOT "0.00"
  "rate": "52.1",                  # NOT "0.0"
  "line_items_count": 2,           # NOT 0
  "first_item": {
    "description": "Pho",
    "category": "Meals & Entertainment",
    "deductible_percentage": 50,
    "citations": ["T4002-P46-...", ...]
  },
  "citations_available": 3         # Citations present
}
```

### Manual Testing Checklist

- [ ] Upload image receipt (.jpg, .png, .heic)
- [ ] Upload PDF receipt (.pdf)
- [ ] Upload with agent mode ON
- [ ] Upload with agent mode OFF
- [ ] Upload with dry run ON
- [ ] Upload with dry run OFF
- [ ] Verify deductible amount displays correctly
- [ ] Verify deductibility rate displays correctly
- [ ] Verify business rules show line items
- [ ] Verify mode indicator shows "Agent Processing"
- [ ] Verify processing summary shows agent details
- [ ] Toggle "Show Details" / "Hide Details" button
- [ ] Process multiple receipts in sequence
- [ ] Check browser console for errors
- [ ] Verify no QuickBooks expense created in dry run mode

### Performance Testing

**Baseline Metrics** (from documentation):
- Agent mode processing: 15-60 seconds (2-agent system)
- Non-agent mode processing: 5-15 seconds (Gemini only)

**Performance Acceptance**:
- [ ] Agent mode processing < 90 seconds (no regression)
- [ ] Non-agent mode processing < 20 seconds (no regression)
- [ ] UI remains responsive during processing
- [ ] No memory leaks after 10+ receipt uploads

### Error Handling Testing

**Test Case: Invalid Response Handling**
```javascript
// Simulate missing fields
const mockResponse = {
  status: "success",
  receipt_info: {},  // Empty
  tax_deductibility: {},  // Empty
  business_rules: {}  // Empty
};

Expected:
✅ UI shows default values (not crash)
✅ Shows "$0.00" gracefully (with empty data)
✅ Shows "No business rules applied" (with empty rules)
```

---

## Rollback Plan

### If Issues Discovered

**Quick Rollback** (revert web_endpoints.py changes):
```bash
git checkout src/quickexpense/api/web_endpoints.py
uv run fastapi dev src/quickexpense/main.py
```

**Partial Rollback** (keep field fixes, revert line items transformation):
1. Keep Change 1 (field mapping fixes)
2. Revert Changes 2, 3, 4 (line items transformation)
3. Result: Shows correct amounts, but not individual line items

### Rollback Decision Criteria

**Trigger rollback if**:
- Non-agent endpoint breaks (regression)
- UI crashes with agent mode enabled
- Processing takes >2 minutes consistently
- QuickBooks creation fails in non-dry-run mode

**Safe to proceed if**:
- Agent mode shows non-zero amounts (even if not perfect)
- Line items display (even if formatting needs adjustment)
- No crashes or errors in browser console
- Non-agent mode unaffected

---

## Implementation Checklist

### Pre-Implementation
- [ ] Read PR #23 changes to understand line-item structure
- [ ] Review orchestrator.py output format
- [ ] Review MultiAgentReceiptResponse model definition
- [ ] Backup current web_endpoints.py

### Implementation Phase
- [ ] Add `_format_line_items_as_rules()` helper function
- [ ] Update field mappings (lines 696, 702)
- [ ] Update business_rules structure (lines 768-790)
- [ ] Update agent_details.full_agent_data (line 867)
- [ ] Run pre-commit hooks: `uv run pre-commit run --all-files`
- [ ] Fix any linting/formatting issues

### Testing Phase
- [ ] Test Case 1.1: Pho Georgia Express (IMG_7597.HEIC)
- [ ] Test Case 1.2: Marriott Hotel (marriot.pdf)
- [ ] Test Case 1.3: Harrods (Harrods.jpg)
- [ ] Test Case 2.1: Non-agent mode regression
- [ ] Test Case 3.1: API response validation
- [ ] Manual testing checklist (all items)
- [ ] Performance testing (timing checks)

### Verification Phase
- [ ] All 7 must-have acceptance criteria met
- [ ] No browser console errors
- [ ] Server logs show successful processing
- [ ] Citations visible in JSON response
- [ ] Pre-commit hooks pass

### Documentation Phase
- [ ] Update CLAUDE.md if needed
- [ ] Add notes to RAG_CITATION_FIX_PLAN.md about UI fix
- [ ] Document any edge cases discovered
- [ ] Update API documentation if structure changed

### Deployment Phase
- [ ] Create commit with conventional commit message
- [ ] Push changes to repository
- [ ] Create PR if team review needed
- [ ] Deploy to staging/production environment
- [ ] Smoke test in production environment

---

## Success Metrics

### Immediate Success (Post-Implementation)

**Quantitative**:
- Citation rate: 100% (already achieved in backend, now visible in UI)
- Line item display rate: 100% (all processed items shown)
- Deductible amount accuracy: 100% (matches backend calculation)
- Non-agent mode regression: 0 failures

**Qualitative**:
- User can see agent processing results
- User can verify tax deductibility calculations
- User can trust the system is working correctly
- User can review individual line item categorizations

### Long-Term Success (Post-Demo)

**User Experience**:
- Reduced confusion about "No business rules applied"
- Increased trust in multi-agent processing
- Better transparency in tax calculations
- Foundation for citation display in UI

**Technical**:
- Clean data flow from backend to UI
- Maintainable code structure
- Extensible for future enhancements (citation rendering)
- No technical debt introduced

---

## Related Documentation

- **PR #23**: feat: Phase 2 programmatic citation injection achieving 100% citation rate
- **RAG_CITATION_FIX_PLAN.md**: Complete Phase 2 implementation documentation
- **CLAUDE.md**: Project architecture and 2-agent system overview
- **MULTI_AGENT_ARCHITECTURE.md**: Detailed agent system documentation

---

## Notes and Assumptions

### Assumptions
1. The `line_items` structure from orchestrator is stable (won't change)
2. UI can handle variable number of line items gracefully
3. Citations array format is stable (`["T4002-P46-a73c204c", ...]`)
4. MultiAgentReceiptResponse model doesn't need modification (just field mapping)
5. User understands that agent mode takes longer than standard mode

### Known Limitations
1. UI doesn't render citations yet (only available in JSON)
2. `qb_account` field may not be in line_items structure (using placeholder)
3. Individual item confidence scores not available (using placeholder)
4. Agent breakdown still references 3-agent system (should be updated to 2-agent)

### Future Enhancements
1. Add UI rendering for citations with links to CRA sources
2. Add line-by-line deductibility breakdown visualization
3. Add category-based color coding for line items
4. Add export functionality for processed results with citations
5. Add confidence score visualization per line item

---

**END OF PLAN**
