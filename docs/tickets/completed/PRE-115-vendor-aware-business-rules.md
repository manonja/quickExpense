# PRE-115: Vendor-Aware Business Rules Enhancement

**Type:** Bug Fix / Enhancement
**Priority:** High (Fixes Production Issue)
**Effort:** 3 Story Points
**Sprint:** Immediate (Hotfix)

## User Story
**As a** small business owner processing hotel receipts
**I want** marketing fees and hotel-specific charges to be correctly categorized as Travel-Lodging
**So that** my expense categorization is accurate and reflects the true nature of hotel-related charges

## Business Value
- **Problem:** Marketing fees from hotels are incorrectly categorized as "Professional Services" instead of "Travel-Lodging"
- **Impact:** Incorrect categorization affects tax reporting and QuickBooks account mapping for hotel expenses
- **Solution:** Vendor-aware business rules that consider hotel context when categorizing fees

## Description
Enhance the business rules engine to be vendor-aware, specifically addressing the miscategorization of hotel marketing fees. The system should understand that when a vendor is identified as a hotel, certain fees (marketing, resort, destination, amenity fees) should be categorized as Travel-Lodging rather than Professional Services.

## User Feedback Analysis
Real user testing with Marriott hotel receipt revealed:

### ✅ **What Works Well:**
- Line item recognition: Perfect accuracy (11/11 items)
- Meals deductibility: Correct 50% limitation
- GST treatment: Proper Input Tax Credit handling
- Overall math: Accurate calculations

### ⚠️ **Critical Issue:**
- **Marketing Fee Miscategorization**: Currently maps to "Professional Services" but should be "Travel-Lodging" for hotels
- **Root Cause**: Rules don't consider vendor context when making categorization decisions
- **Confidence Issue**: 85% confidence indicates uncertainty in the current rule

## Acceptance Criteria

### AC1: Hotel-Specific Marketing Fee Rule
- [ ] Create high-priority rule "Hotel Marketing and Service Fees" (priority 110+)
- [ ] Rule matches marketing fees specifically when vendor is a hotel
- [ ] Maps to Travel-Lodging category and appropriate QuickBooks account
- [ ] Achieves >90% confidence for hotel marketing fees

### AC2: Vendor Context Awareness
- [ ] Business rules engine considers vendor patterns when selecting rules
- [ ] Vendor-category conflict detection identifies potential mismatches
- [ ] Confidence scoring adjusts based on vendor-category fit
- [ ] Rules can specify vendor type requirements/exclusions

### AC3: Enhanced Rule Priority Logic
- [ ] Hotel-specific rules take precedence over generic rules when vendor matches
- [ ] Vendor-aware rules have higher effective priority for matching vendors
- [ ] Fallback to generic rules when vendor context doesn't match
- [ ] Clear logging of rule selection reasoning

### AC4: Validation and Warnings
- [ ] System flags potential vendor-category conflicts
- [ ] CLI output shows vendor context influence on categorization
- [ ] Confidence scores reflect vendor-category alignment
- [ ] Manual review flagged for suspicious categorizations

### AC5: Comprehensive Hotel Fee Coverage
- [ ] Support for marketing fees, resort fees, destination fees, amenity fees
- [ ] All hotel-related fees map to Travel-Lodging when vendor is hotel
- [ ] Maintain existing behavior for non-hotel vendors
- [ ] Clear documentation of hotel fee patterns

## Technical Implementation

### Enhanced Business Rules Configuration
```json
{
  "id": "hotel_marketing_fees",
  "priority": 110,
  "name": "Hotel Marketing and Service Fees",
  "description": "Marketing and service fees from hotels - categorize as lodging",
  "conditions": {
    "description_keywords": ["marketing fee", "resort fee", "destination fee", "amenity fee", "facility fee"],
    "vendor_patterns": ["*hotel*", "*marriott*", "*hilton*", "*courtyard*", "*inn*", "*resort*", "*hyatt*"],
    "amount_min": 1.0,
    "amount_max": 100.0
  },
  "actions": {
    "category": "Travel-Lodging",
    "deductibility_percentage": 100,
    "qb_account": "Travel - Lodging",
    "tax_treatment": "standard",
    "confidence_boost": 0.2,
    "compliance_note": "Hotel fees categorized as accommodation costs"
  }
}
```

### Vendor Context Logic
- Implement `select_best_rule_with_vendor_context()` method
- Add vendor-category validation scoring
- Create conflict detection for mismatched vendor types
- Enhance confidence calculation with vendor alignment

## Expected Results

### Before (Current Issue):
```
Marketing Fee:
  Rule Applied: Marketing and Service Fees
  Category: Professional Services
  QuickBooks Account: Professional Fees
  Confidence: 85%
```

### After (Fixed):
```
Marketing Fee:
  Rule Applied: Hotel Marketing and Service Fees
  Category: Travel-Lodging
  QuickBooks Account: Travel - Lodging
  Confidence: 95%
  Vendor Context: Hotel fees categorized as lodging
```

### Updated Tax Summary:
```
=== Tax Deductibility Summary ===
Total Amount: $535.46
Deductible Amount: $464.20 (86.7%)

Deductible by Category:
  • Travel-Meals: $71.26 (50% of $142.52)
  • Travel-Lodging: $360.50 (includes marketing fees) ← FIXED
  • Tax-GST/HST: $18.02 (100% as ITC)
  • Travel-Taxes: $14.42 (Tourism levy)
```

## Testing Requirements

### Unit Tests
- [ ] Test hotel marketing fee categorization specifically
- [ ] Test vendor context influence on rule selection
- [ ] Test confidence scoring with vendor alignment
- [ ] Test conflict detection for vendor-category mismatches

### Integration Tests
- [ ] Validate against real Marriott hotel receipt
- [ ] Test with various hotel brands and fee types
- [ ] Ensure non-hotel vendors still work correctly
- [ ] Performance testing with vendor context processing

### Regression Tests
- [ ] All existing tests continue to pass
- [ ] No changes to non-hotel receipt processing
- [ ] Existing confidence scores maintained for other categories

## Definition of Done
- [ ] Marketing fees from hotels categorized as Travel-Lodging
- [ ] Confidence scores >90% for hotel-specific patterns
- [ ] All existing functionality preserved
- [ ] Pre-commit hooks pass (ruff, mypy, black, pyright)
- [ ] Real Marriott receipt test case validates correctly
- [ ] CLI output enhanced with vendor context information
- [ ] Comprehensive test coverage for new functionality

## Dependencies
- Existing business rules engine (PRE-107) ✅ Completed
- Enhanced models for multi-category expenses (PRE-106) ✅ Completed
- CLI integration (PRE-113) ✅ Completed

## Risks and Mitigation
- **Risk:** Changes affect existing categorization
- **Mitigation:** Vendor-specific rules only affect hotel vendors
- **Risk:** Performance impact of vendor context processing
- **Mitigation:** Efficient pattern matching and caching

## Success Metrics
- Marketing fee categorization accuracy: 100% for hotels
- Overall confidence improvement: >5% for hotel receipts
- Zero regression in existing functionality
- User feedback validation: "92/100" → "98/100" score target
