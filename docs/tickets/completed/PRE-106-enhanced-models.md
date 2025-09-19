# PRE-106: Enhanced Models for Multi-Category Expenses

**Type:** Story
**Priority:** High
**Effort:** 3 Story Points
**Sprint:** Foundation Layer

## User Story
**As a** small business owner
**I want** to process receipts with multiple expense categories (like hotel bills with accommodation and meals)
**So that** each line item is properly categorized for tax deductibility and accounting purposes

## Business Value
- **Problem:** Current models only support single-category expenses, making hotel bills with mixed accommodation/meals impossible to process correctly
- **Impact:** Incorrect tax deductibility calculations, CRA compliance issues, manual work for complex receipts
- **Solution:** Enhanced models supporting line-item level categorization with different deductibility percentages

## Description
Enhance the core expense models to support multi-category receipts where different line items have different tax treatments, deductibility percentages, and QuickBooks account mappings. This is essential for complex receipts like hotel bills that contain both 100% deductible accommodation charges and 50% deductible meal charges.

## Acceptance Criteria

### AC1: Enhanced LineItem Model
- [ ] LineItem model includes `deductibility_percentage` field (0-100%)
- [ ] LineItem model includes `category` field for expense categorization
- [ ] LineItem model includes `account_mapping` field for QB account assignment
- [ ] LineItem model includes `tax_treatment` field for tax compliance rules
- [ ] All monetary fields use Decimal for precision
- [ ] Validation ensures deductibility_percentage is between 0-100
- [ ] Model supports confidence scoring for AI-extracted categorizations

### AC2: Enhanced Expense Model
- [ ] Expense model supports multiple line items with different categories
- [ ] Expense model calculates total deductible amount automatically
- [ ] Expense model supports mixed currencies with base currency conversion
- [ ] Expense model includes `business_rules_applied` field tracking which rules were used
- [ ] Model validation ensures line item totals match expense total
- [ ] Model includes audit trail for categorization decisions

### AC3: Business Rule Integration Support
- [ ] Models include fields to track which business rules were applied
- [ ] Models support rule override capabilities for manual adjustments
- [ ] Models include metadata for rule engine integration
- [ ] Models support validation against business rule constraints

### AC4: Tax Compliance Support
- [ ] Models support Canadian tax compliance (CRA requirements)
- [ ] Models track GST/HST treatment separately from deductibility
- [ ] Models support foreign currency transactions with exchange rate tracking
- [ ] Models include fields for tax year and compliance period
- [ ] Models support ITA Section 67.1 (meals limitation) compliance

## Technical Implementation

### Files to Modify
- `src/quickexpense/models/expense.py` - Enhance core models
- `src/quickexpense/models/receipt.py` - Update receipt extraction models
- `tests/unit/test_models.py` - Add comprehensive model tests

### Key Model Changes
```python
class EnhancedLineItem(BaseModel):
    """Enhanced line item supporting multi-category expenses."""
    description: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    quantity: int = Field(default=1, ge=1)
    category: str = Field(..., description="Expense category (e.g., Travel-Lodging)")
    deductibility_percentage: int = Field(ge=0, le=100, description="Tax deductibility %")
    account_mapping: str | None = Field(None, description="QuickBooks account ID")
    tax_treatment: str = Field(default="standard", description="Tax treatment type")
    currency: str = Field(default="CAD", pattern="^[A-Z]{3}$")
    confidence_score: float = Field(ge=0, le=1, description="AI extraction confidence")
    business_rule_id: str | None = Field(None, description="Applied business rule ID")

class EnhancedExpense(BaseModel):
    """Enhanced expense supporting multi-category processing."""
    vendor_name: str = Field(..., min_length=1, max_length=100)
    date: date
    total_amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="CAD", pattern="^[A-Z]{3}$")
    line_items: list[EnhancedLineItem] = Field(..., min_items=1)
    business_rules_applied: list[str] = Field(default_factory=list)
    total_deductible_amount: Decimal | None = None  # Auto-calculated
    foreign_exchange_rate: Decimal | None = None
    payment_method: str
    payment_account: str | None = None
    processing_metadata: dict[str, Any] = Field(default_factory=dict)
```

## Testing Requirements

### Unit Tests
- [ ] Model validation tests for all new fields
- [ ] Edge case tests (0% and 100% deductibility)
- [ ] Currency validation and conversion tests
- [ ] Line item total validation tests
- [ ] Business rule tracking tests
- [ ] Confidence score validation tests

### Integration Tests
- [ ] Test with Marriott hotel bill data structure
- [ ] Test with single-category receipt (office supplies)
- [ ] Test with mixed-currency scenarios
- [ ] Test business rule application tracking
- [ ] Test with zero-price line items edge case

### Test Data Examples
```json
{
  "vendor_name": "Courtyard by Marriott Edmonton",
  "date": "2025-04-24",
  "total_amount": 535.46,
  "currency": "CAD",
  "line_items": [
    {
      "description": "Room Charge",
      "amount": 175.00,
      "category": "Travel-Lodging",
      "deductibility_percentage": 100,
      "tax_treatment": "standard",
      "confidence_score": 0.95
    },
    {
      "description": "Restaurant Room Charge",
      "amount": 40.70,
      "category": "Travel-Meals",
      "deductibility_percentage": 50,
      "tax_treatment": "meals_limitation",
      "confidence_score": 0.88
    },
    {
      "description": "GST",
      "amount": 18.02,
      "category": "Tax-GST",
      "deductibility_percentage": 100,
      "tax_treatment": "input_tax_credit",
      "confidence_score": 1.0
    }
  ],
  "business_rules_applied": ["hotel_accommodation", "restaurant_meals", "gst_processing"]
}
```

## Dependencies
- None (foundational ticket)

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] Unit tests pass with >95% coverage on new model code
- [ ] Integration tests validate real-world scenarios
- [ ] Models work with existing Gemini AI extraction service
- [ ] Models integrate with existing QuickBooks service
- [ ] Code review completed and approved
- [ ] Documentation updated (model schemas, API docs)
- [ ] Backward compatibility maintained with existing expense records

## Validation Scenarios

### Scenario 1: Marriott Hotel Bill (Primary Use Case)
**Given** a hotel bill with room charges ($350), restaurant charges ($142.52), and GST ($18.02)
**When** the expense is processed through enhanced models
**Then**
- Room charges are marked 100% deductible with "Travel-Lodging" category
- Restaurant charges are marked 50% deductible with "Travel-Meals" category
- GST is marked 100% ITC claimable with "Tax-GST" category
- Total deductible amount is calculated correctly: $350 + $71.26 + $18.02 = $439.28

### Scenario 2: Office Supply Receipt (Single Category)
**Given** a single-category office supply receipt with multiple items
**When** processed through enhanced models
**Then** all line items have same category "Office Supplies" and 100% deductibility

### Scenario 3: Mixed Currency Transaction
**Given** a CAD receipt paid with USD credit card
**When** processed with foreign exchange rate (e.g., 1.35 CAD/USD)
**Then** models track both CAD amounts and USD payment with exchange rate

### Scenario 4: Rule Override Scenario
**Given** an AI-categorized expense with low confidence scores
**When** a user manually overrides categorization
**Then** models track both original and overridden categorizations with audit trail

## Risk Mitigation
- **Breaking Changes:** Maintain backward compatibility with existing Expense model
- **Performance:** Optimize model validation for large receipts (50+ line items)
- **Data Migration:** Existing expense records remain functional without line-item details
- **Validation Complexity:** Comprehensive field validation without over-constraining flexibility

## Success Metrics
- Models handle complex multi-category receipts without errors
- Deductibility calculations are accurate for Canadian tax compliance
- Processing time remains under 500ms for typical receipts
- AI confidence scores correlate with categorization accuracy >90%
