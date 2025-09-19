# PRE-110: Enhanced QuickBooks Multi-Line Integration

**Type:** Story
**Priority:** Medium
**Effort:** 4 Story Points
**Sprint:** Processing Engine Layer

## User Story
**As a** small business owner
**I want** complex receipts automatically split into multiple QuickBooks entries with proper categorization
**So that** my accounting is accurate and complies with tax regulations without manual work

## Business Value
- **Problem:** Current QB integration creates single expense entries, losing categorization detail needed for tax compliance
- **Impact:** Incorrect tax deductions, manual accounting work, CRA compliance issues
- **Solution:** Multi-line QB integration that creates separate entries per category with proper account mapping

## Description
Enhance the QuickBooks integration to handle multi-category expenses by creating multiple purchase/expense entries with appropriate account mappings, deductibility tracking, and tax treatment. The system should maintain data integrity while optimizing for QuickBooks performance and user experience.

## Acceptance Criteria

### AC1: Multi-Category Expense Creation
- [ ] Creates separate QB Purchase entries for different expense categories
- [ ] Groups line items by account and category for efficient submission
- [ ] Maintains reference to original receipt across all entries
- [ ] Supports both Purchase and Expense transaction types based on payment method
- [ ] Handles partial expense splits (accommodation vs meals) correctly
- [ ] Links related entries with reference numbers for traceability

### AC2: Advanced Account Mapping
- [ ] Automatically maps categories to appropriate QB Chart of Accounts
- [ ] Creates missing expense accounts when configured to do so
- [ ] Handles account hierarchy (parent/child account relationships)
- [ ] Supports custom account mapping overrides per business
- [ ] Validates account types match expense categories
- [ ] Maps payment methods to correct bank/credit card accounts

### AC3: Tax Treatment Integration
- [ ] Creates separate entries for different tax treatments (100% vs 50% deductible)
- [ ] Handles GST/HST Input Tax Credits in separate account lines
- [ ] Supports foreign currency transactions with exchange rate tracking
- [ ] Includes tax compliance metadata in QB entry descriptions
- [ ] Creates memo fields with deductibility percentages for audit trails
- [ ] Handles capital asset vs expense determination

### AC4: Payment Method Intelligence
- [ ] Detects payment method from receipt data and business context
- [ ] Maps to appropriate bank accounts or credit cards in QB
- [ ] Handles foreign currency payments (USD card, CAD receipt)
- [ ] Creates appropriate exchange rate adjustments when needed
- [ ] Supports multiple payment accounts per business
- [ ] Validates payment account existence and type

### AC5: Error Handling and Validation
- [ ] Validates all QB entries before submission
- [ ] Handles QB API rate limiting gracefully
- [ ] Provides detailed error messages for failed submissions
- [ ] Supports retry logic for transient failures
- [ ] Rolls back partial submissions on errors
- [ ] Logs all QB interactions for debugging and audit

## Technical Implementation

### Files to Modify/Create
- `src/quickexpense/services/quickbooks.py` - Enhance existing QB service
- `src/quickexpense/services/qb_entry_builder.py` - New QB entry construction
- `src/quickexpense/models/quickbooks.py` - Enhanced QB models
- `src/quickexpense/services/account_mapper.py` - Account mapping logic
- `tests/services/test_quickbooks_enhanced.py` - Comprehensive tests

### Enhanced QuickBooks Service
```python
class EnhancedQuickBooksService:
    """Enhanced QB service supporting multi-category expenses."""

    def __init__(
        self,
        client: QuickBooksClient,
        account_mapper: AccountMapper,
        entry_builder: QBEntryBuilder
    ):
        self.client = client
        self.account_mapper = account_mapper
        self.entry_builder = entry_builder
        self.submission_history: list[SubmissionRecord] = []

    async def create_multi_category_expense(
        self,
        processed_expense: ProcessedExpense
    ) -> list[QBSubmissionResult]:
        """Create multiple QB entries for complex expense."""

        try:
            # 1. Validate processed expense
            self._validate_expense_data(processed_expense)

            # 2. Map accounts and validate they exist
            account_mappings = await self.account_mapper.map_accounts(
                processed_expense.categorized_items
            )

            # 3. Group items by QB entry requirements
            entry_groups = self.entry_builder.group_for_submission(
                processed_expense.categorized_items,
                account_mappings
            )

            # 4. Create QB entries for each group
            results = []
            for group in entry_groups:
                qb_entry = await self.entry_builder.build_purchase_entry(
                    group, processed_expense.original_receipt
                )
                result = await self._submit_entry(qb_entry)
                results.append(result)

            # 5. Link entries with cross-references
            await self._link_related_entries(results)

            # 6. Log submission record
            self._log_submission(processed_expense, results)

            return results

        except Exception as e:
            # Rollback any partial submissions
            await self._rollback_submissions(results)
            raise QBSubmissionError(f"Multi-category submission failed: {e}") from e

class QBEntryBuilder:
    """Builds QuickBooks entries from categorized expenses."""

    def group_for_submission(
        self,
        categorized_items: list[CategorizedLineItem],
        account_mappings: dict[str, AccountInfo]
    ) -> list[EntryGroup]:
        """Group line items for optimal QB submission."""

        groups: dict[str, EntryGroup] = {}

        for item in categorized_items:
            # Group by: account + tax_treatment + payment_method
            group_key = f"{item.qb_account}_{item.tax_treatment}_{item.payment_method}"

            if group_key not in groups:
                groups[group_key] = EntryGroup(
                    account=account_mappings[item.qb_account],
                    tax_treatment=item.tax_treatment,
                    payment_method=item.payment_method,
                    items=[]
                )

            groups[group_key].items.append(item)

        return list(groups.values())

    async def build_purchase_entry(
        self,
        entry_group: EntryGroup,
        original_receipt: ExtractedReceipt
    ) -> QBPurchaseEntry:
        """Build a QB Purchase entry from grouped items."""

        total_amount = sum(item.amount for item in entry_group.items)

        # Build line items for QB
        line_items = []
        for item in entry_group.items:
            line_items.append({
                "Amount": float(item.amount),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {
                        "value": entry_group.account.id,
                        "name": entry_group.account.name
                    }
                },
                "Description": self._build_line_description(item)
            })

        # Handle GST/HST if applicable
        if entry_group.tax_treatment == "input_tax_credit":
            # GST line items handled separately
            pass

        return QBPurchaseEntry(
            vendor_ref=original_receipt.vendor_name,
            total_amount=total_amount,
            transaction_date=original_receipt.transaction_date,
            line_items=line_items,
            payment_account=self._determine_payment_account(entry_group),
            memo=self._build_entry_memo(entry_group, original_receipt),
            currency=original_receipt.currency
        )

class AccountMapper:
    """Maps expense categories to QuickBooks accounts."""

    async def map_accounts(
        self,
        categorized_items: list[CategorizedLineItem]
    ) -> dict[str, AccountInfo]:
        """Map categories to QB accounts, creating if necessary."""

        mappings = {}
        required_accounts = {item.qb_account for item in categorized_items}

        for account_name in required_accounts:
            # First try to find existing account
            account = await self._find_account(account_name)

            if not account:
                # Create account if configured to do so
                account = await self._create_account_if_allowed(account_name)

            if account:
                mappings[account_name] = account
            else:
                raise AccountMappingError(f"Cannot map to account: {account_name}")

        return mappings
```

### Models
```python
class EntryGroup(BaseModel):
    """Group of line items for single QB entry."""
    account: AccountInfo
    tax_treatment: str
    payment_method: str
    items: list[CategorizedLineItem]

class QBPurchaseEntry(BaseModel):
    """QuickBooks Purchase entry data."""
    vendor_ref: str
    total_amount: Decimal
    transaction_date: date
    line_items: list[dict[str, Any]]
    payment_account: str
    memo: str
    currency: str
    reference_number: str | None = None

class QBSubmissionResult(BaseModel):
    """Result of QB entry submission."""
    entry_id: str
    entry_type: str
    status: str
    amount: Decimal
    account: str
    reference_number: str
    submission_timestamp: datetime
    errors: list[str] = Field(default_factory=list)
```

## Testing Requirements

### Unit Tests
- [ ] Entry grouping logic tests
- [ ] Account mapping tests with missing accounts
- [ ] QB entry building tests for different scenarios
- [ ] Error handling and rollback tests
- [ ] Payment method detection tests
- [ ] Currency handling tests

### Integration Tests
- [ ] End-to-end Marriott hotel bill to QB submission
- [ ] Multi-category receipt processing and submission
- [ ] Foreign currency transaction handling
- [ ] Account creation workflow tests
- [ ] QB API rate limiting handling tests
- [ ] Partial failure and rollback tests

### Test Scenarios
```python
# Marriott Hotel Bill QB Integration Test
{
    "input": {
        "vendor": "Courtyard by Marriott Edmonton",
        "categorized_items": [
            {"category": "Travel-Lodging", "amount": 175.00, "deductibility": 100},
            {"category": "Travel-Meals", "amount": 40.70, "deductibility": 50},
            {"category": "Tax-GST", "amount": 9.01, "deductibility": 100}
        ]
    },
    "expected_qb_entries": [
        {
            "account": "Travel - Lodging",
            "amount": 175.00,
            "memo": "Hotel accommodation (100% deductible)"
        },
        {
            "account": "Travel - Meals & Entertainment",
            "amount": 40.70,
            "memo": "Business meals (50% deductible per ITA 67.1)"
        },
        {
            "account": "GST/HST Paid on Purchases",
            "amount": 9.01,
            "memo": "Input Tax Credit"
        }
    ]
}
```

## Dependencies
- **PRE-106: Enhanced Models** - Required for categorized line item data
- **PRE-109: Expense Processor** - Required for processed expense input

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] Creates accurate multi-category QB entries
- [ ] Handles complex receipts like hotel bills correctly
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate real QB submission
- [ ] Error handling covers all failure scenarios
- [ ] Performance meets requirements (5+ entries per receipt)
- [ ] Code review completed and approved
- [ ] Documentation includes QB setup and mapping guide

## Validation Scenarios

### Scenario 1: Marriott Hotel Bill Submission
**Given** processed Marriott hotel bill with 3 categories
**When** submitted to QuickBooks
**Then**
- 3 separate Purchase entries created
- Accommodation entry: Travel-Lodging account, 100% deductible memo
- Meals entry: Travel-Meals account, 50% deductible memo
- GST entry: GST Paid account, Input Tax Credit memo
- All entries linked with reference numbers

### Scenario 2: Single Category Receipt
**Given** simple office supply receipt
**When** submitted to QuickBooks
**Then** single Purchase entry created with all items grouped

### Scenario 3: Foreign Currency Transaction
**Given** CAD receipt paid with USD credit card
**When** submitted to QuickBooks
**Then** entries created in CAD with USD payment account and exchange rate notes

### Scenario 4: Missing Account Handling
**Given** expense category mapping to non-existent QB account
**When** submitted to QuickBooks
**Then** account created automatically (if configured) or clear error returned

## Risk Mitigation
- **Partial Failures:** Comprehensive rollback mechanism for multi-entry submissions
- **QB Rate Limits:** Intelligent retry logic with exponential backoff
- **Data Integrity:** Validation at every step, transaction-like behavior
- **Account Management:** Safe account creation with proper validation

## Success Metrics
- 100% data accuracy in QB entries vs original receipt
- Multi-category receipts submitted in <5 seconds
- Zero data loss during complex submissions
- 95%+ automatic account mapping success rate
- Complete audit trail for all QB transactions
