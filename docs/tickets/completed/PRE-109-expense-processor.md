# PRE-109: Generic Expense Processing Engine

**Type:** Story
**Priority:** Medium
**Effort:** 5 Story Points
**Sprint:** Processing Engine Layer

## User Story
**As a** small business owner
**I want** a single expense processor that handles any type of receipt (hotel bills, office supplies, meals, equipment)
**So that** I get consistent, accurate categorization and tax treatment regardless of expense complexity

## Business Value
- **Problem:** Current system processes single-category expenses only, requiring separate logic for different expense types
- **Impact:** Inconsistent processing, maintenance overhead, inability to handle complex receipts like hotel bills
- **Solution:** Universal expense processor using business rules to handle any expense type consistently

## Description
Create a generic expense processing engine that takes extracted receipt data and applies business rules to categorize line items, calculate deductibility, map to QuickBooks accounts, and generate appropriate expense entries. The processor should handle simple single-category receipts and complex multi-category receipts through the same unified interface.

## Acceptance Criteria

### AC1: Universal Expense Processing Interface
- [ ] Single processor handles any expense type (travel, office, meals, equipment, etc.)
- [ ] Processes both single-category and multi-category receipts
- [ ] Takes extracted receipt data and business rules as input
- [ ] Returns categorized expense data ready for QuickBooks submission
- [ ] Supports batch processing of multiple receipts
- [ ] Provides detailed processing logs for audit and debugging

### AC2: Business Rules Integration
- [ ] Integrates with business rules engine (PRE-107) for categorization
- [ ] Applies rules to each line item independently
- [ ] Handles rule conflicts using priority-based resolution
- [ ] Logs which rules were applied for each line item
- [ ] Supports rule overrides for manual corrections
- [ ] Validates business rule constraints and compliance

### AC3: Multi-Category Expense Handling
- [ ] Splits complex receipts into multiple categorized line items
- [ ] Calculates total deductible amounts per category
- [ ] Handles mixed deductibility percentages (100%, 50%, 0%)
- [ ] Groups line items by QuickBooks account for efficient submission
- [ ] Maintains line item traceability to original receipt
- [ ] Supports foreign currency conversion and tracking

### AC4: Tax Compliance Processing
- [ ] Applies Canadian tax rules (CRA compliance) automatically
- [ ] Handles GST/HST Input Tax Credit calculations
- [ ] Implements meal deductibility limitations (ITA Section 67.1)
- [ ] Supports capital asset vs expense determination
- [ ] Tracks foreign exchange implications
- [ ] Generates compliance reports and documentation

### AC5: Validation and Quality Assurance
- [ ] Validates processed data against business rules
- [ ] Detects and flags potential categorization errors
- [ ] Provides confidence scores for AI-extracted data
- [ ] Supports manual review workflow for low-confidence items
- [ ] Ensures mathematical accuracy (totals, tax calculations)
- [ ] Validates QuickBooks account mappings exist

## Technical Implementation

### Files to Create
- `src/quickexpense/services/expense_processor.py` - Main processing engine
- `src/quickexpense/models/processed_expense.py` - Processed expense models
- `src/quickexpense/services/tax_calculator.py` - Tax compliance calculations
- `src/quickexpense/services/validation.py` - Data validation utilities
- `tests/services/test_expense_processor.py` - Comprehensive tests

### Core Architecture
```python
class UniversalExpenseProcessor:
    """Generic expense processor for all receipt types."""

    def __init__(
        self,
        business_rules_engine: BusinessRuleEngine,
        tax_calculator: TaxCalculator,
        validator: ExpenseValidator
    ):
        self.rules_engine = business_rules_engine
        self.tax_calculator = tax_calculator
        self.validator = validator
        self.processing_history: list[ProcessingRecord] = []

    async def process_expense(
        self,
        extracted_receipt: ExtractedReceipt,
        processing_context: ProcessingContext
    ) -> ProcessedExpense:
        """Process extracted receipt data into categorized expense."""

        start_time = time.time()

        try:
            # 1. Validate input data
            self.validator.validate_receipt(extracted_receipt)

            # 2. Process each line item through business rules
            categorized_items = []
            for line_item in extracted_receipt.line_items:
                rule_result = await self.rules_engine.apply_rules(
                    line_item,
                    processing_context
                )
                categorized_item = self._create_categorized_item(line_item, rule_result)
                categorized_items.append(categorized_item)

            # 3. Handle uncategorized amounts (totals mismatch)
            categorized_items = await self._handle_uncategorized_amounts(
                extracted_receipt, categorized_items
            )

            # 4. Calculate tax implications
            tax_summary = await self.tax_calculator.calculate_tax_treatment(
                categorized_items, processing_context
            )

            # 5. Group by QuickBooks accounts
            qb_entries = self._group_for_quickbooks_submission(categorized_items)

            # 6. Final validation
            processed_expense = ProcessedExpense(
                original_receipt=extracted_receipt,
                categorized_items=categorized_items,
                tax_summary=tax_summary,
                quickbooks_entries=qb_entries,
                processing_metadata=self._create_metadata(start_time)
            )

            self.validator.validate_processed_expense(processed_expense)

            # 7. Log processing record
            self._log_processing_record(processed_expense)

            return processed_expense

        except Exception as e:
            logger.error(f"Expense processing failed: {e}")
            raise ExpenseProcessingError(f"Processing failed: {e}") from e

class TaxCalculator:
    """Canadian tax compliance calculations."""

    async def calculate_tax_treatment(
        self,
        categorized_items: list[CategorizedLineItem],
        context: ProcessingContext
    ) -> TaxSummary:
        """Calculate tax implications for categorized expenses."""

        summary = TaxSummary()

        for item in categorized_items:
            # Apply deductibility percentage
            deductible_amount = item.amount * (item.deductibility_percentage / 100)
            summary.total_deductible += deductible_amount

            # Handle GST/HST Input Tax Credits
            if item.tax_treatment == "input_tax_credit":
                summary.gst_itc_claimable += item.amount

            # Apply meal limitations (CRA ITA 67.1)
            if item.tax_treatment == "meals_limitation":
                summary.meals_subject_to_limitation += item.amount
                summary.meals_deductible += item.amount * 0.5

            # Track by category for reporting
            summary.by_category[item.category] = summary.by_category.get(
                item.category, Decimal('0')
            ) + deductible_amount

        return summary
```

### Models
```python
class CategorizedLineItem(BaseModel):
    """Line item with applied business rules."""
    original_item: LineItem
    category: str
    deductibility_percentage: int
    tax_treatment: str
    qb_account: str
    confidence_score: float
    applied_rule: str
    amount: Decimal
    currency: str

class ProcessedExpense(BaseModel):
    """Fully processed expense ready for QuickBooks."""
    original_receipt: ExtractedReceipt
    categorized_items: list[CategorizedLineItem]
    tax_summary: TaxSummary
    quickbooks_entries: list[QBEntry]
    processing_metadata: ProcessingMetadata
    validation_results: ValidationResults

class TaxSummary(BaseModel):
    """Tax compliance summary."""
    total_amount: Decimal
    total_deductible: Decimal
    gst_itc_claimable: Decimal
    meals_subject_to_limitation: Decimal
    meals_deductible: Decimal
    by_category: dict[str, Decimal] = Field(default_factory=dict)
    compliance_notes: list[str] = Field(default_factory=list)

class QBEntry(BaseModel):
    """QuickBooks entry data."""
    account: str
    amount: Decimal
    category: str
    description: str
    line_items: list[CategorizedLineItem]
    tax_treatment: str
```

## Testing Requirements

### Unit Tests
- [ ] Single-category expense processing tests
- [ ] Multi-category expense processing tests (hotel bills)
- [ ] Business rule application tests
- [ ] Tax calculation accuracy tests
- [ ] Validation and error handling tests
- [ ] Currency conversion tests

### Integration Tests
- [ ] End-to-end Marriott hotel bill processing
- [ ] Office supply receipt processing
- [ ] Restaurant receipt processing
- [ ] Equipment purchase processing
- [ ] Mixed currency expense processing
- [ ] Batch processing tests

### Test Scenarios
```python
# Marriott Hotel Bill Test
{
    "vendor_name": "Courtyard by Marriott Edmonton",
    "line_items": [
        {"description": "Room Charge", "amount": 175.00},
        {"description": "Restaurant Room Charge", "amount": 40.70},
        {"description": "Tourism Levy", "amount": 7.21},
        {"description": "GST", "amount": 9.01}
    ],
    "expected_processing": {
        "categories": ["Travel-Lodging", "Travel-Meals", "Travel-Lodging", "Tax-GST"],
        "deductibility": [100, 50, 100, 100],
        "qb_accounts": ["Travel - Lodging", "Travel - Meals", "Travel - Lodging", "GST Paid"],
        "total_deductible": 211.56  # 175 + 20.35 + 7.21 + 9.01
    }
}
```

## Dependencies
- **PRE-106: Enhanced Models** - Required for categorized line item models
- **PRE-107: Business Rules** - Required for expense categorization engine

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] Processes complex multi-category receipts accurately
- [ ] Tax calculations comply with Canadian regulations
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate real-world scenarios
- [ ] Performance meets requirements (<1 second per receipt)
- [ ] Code review completed and approved
- [ ] Documentation includes processing flow and API guide

## Validation Scenarios

### Scenario 1: Marriott Hotel Bill (Primary Use Case)
**Given** extracted Marriott hotel bill with room charges, meals, fees, and GST
**When** processed through the expense engine
**Then**
- Room charges and fees → Travel-Lodging, 100% deductible
- Meals → Travel-Meals, 50% deductible
- GST → Input Tax Credit, 100% claimable
- Total deductible amount calculated correctly
- 3 separate QuickBooks entries created

### Scenario 2: Simple Office Supply Receipt
**Given** single-category office supply receipt
**When** processed through the expense engine
**Then** all items categorized as Office Supplies, 100% deductible, single QB entry

### Scenario 3: Mixed Currency Transaction
**Given** CAD receipt paid with USD credit card
**When** processed with exchange rate context
**Then** amounts tracked in both currencies with proper conversion

### Scenario 4: Low Confidence Categorization
**Given** receipt with ambiguous line items
**When** processed through the engine
**Then** low-confidence items flagged for manual review

## Risk Mitigation
- **Calculation Accuracy:** Comprehensive validation of all mathematical operations
- **Rule Conflicts:** Priority-based resolution with detailed logging
- **Performance:** Optimize for typical receipt sizes (5-20 line items)
- **Data Integrity:** Ensure processed data maintains traceability to original receipt

## Success Metrics
- Processes 95%+ of receipts without manual intervention
- Tax calculations 100% accurate for auditing
- Processing time <1 second for typical receipts
- Categorization accuracy >90% for common business expenses
- Zero data loss during processing (full traceability maintained)
