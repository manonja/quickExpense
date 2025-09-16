# PRE-113: Universal CLI & API Interface

**Type:** Story
**Priority:** Low
**Effort:** 3 Story Points
**Sprint:** User Experience Layer

## User Story
**As a** small business owner
**I want** a single, intuitive interface to upload any receipt type and see detailed categorization results
**So that** I can efficiently process expenses without learning different commands for different receipt types

## Business Value
- **Problem:** Current CLI requires users to understand different processing modes for different receipt types
- **Impact:** Poor user experience, learning curve, potential for user errors
- **Solution:** Universal interface that handles all receipt types with intelligent output formatting

## Description
Create a universal CLI and API interface that automatically handles any receipt type (PDF, images) and provides rich, contextual output showing categorization, tax implications, and QuickBooks integration results. The interface should be intuitive for non-technical users while providing detailed information for accounting purposes.

## Acceptance Criteria

### AC1: Universal Upload Command
- [ ] Single `quickexpense upload <file>` command handles all file types
- [ ] Auto-detection of file format (PDF, JPEG, PNG, etc.)
- [ ] Automatic processing through entire pipeline (extraction → categorization → QB creation)
- [ ] Support for batch uploads of multiple files
- [ ] Progress indicators for long-running operations
- [ ] Intelligent error messages with actionable suggestions

### AC2: Rich Output Formatting
- [ ] Detailed categorization breakdown showing line items and deductibility
- [ ] Tax compliance summary with Canadian-specific insights
- [ ] QuickBooks entry preview before submission
- [ ] Foreign currency handling with exchange rate information
- [ ] Confidence scores and flagged items requiring review
- [ ] Output format options (human-readable, JSON, CSV)

### AC3: Enhanced API Endpoints
- [ ] Universal `/api/v1/receipts/process` endpoint for any file type
- [ ] Supports both single file and batch processing
- [ ] Returns comprehensive processing results with categorization details
- [ ] Includes validation results and confidence scoring
- [ ] Provides QuickBooks integration status and entry IDs
- [ ] Supports processing options and business context parameters

### AC4: Interactive Features
- [ ] `--dry-run` mode shows processing results without QB submission
- [ ] `--review` mode allows manual correction of low-confidence categorizations
- [ ] `--explain` mode provides detailed reasoning for categorization decisions
- [ ] Support for processing configuration (business context, custom rules)
- [ ] Ability to save and reuse processing profiles
- [ ] Integration with existing auth and status commands

### AC5: Business Intelligence Output
- [ ] Expense summaries by category and time period
- [ ] Tax optimization insights and recommendations
- [ ] Deductibility analysis with compliance notes
- [ ] Processing statistics and accuracy metrics
- [ ] Export capabilities for accounting software integration
- [ ] Audit trail with full processing history

## Technical Implementation

### Files to Modify/Create
- `src/quickexpense/cli.py` - Enhance existing CLI with universal interface
- `src/quickexpense/api/routes.py` - Add universal processing endpoints
- `src/quickexpense/services/output_formatter.py` - Rich output formatting
- `src/quickexpense/services/cli_processor.py` - CLI processing orchestration
- `src/quickexpense/models/api_responses.py` - Enhanced API response models

### Enhanced CLI Interface
```python
class UniversalCLI:
    """Enhanced CLI with universal receipt processing."""

    def __init__(self):
        self.processor = CLIProcessor()
        self.formatter = OutputFormatter()
        self.config_manager = ConfigManager()

    async def upload_command(
        self,
        file_path: str,
        dry_run: bool = False,
        output_format: str = "human",
        review_mode: bool = False,
        explain: bool = False,
        business_context: str | None = None
    ) -> None:
        """Universal upload command for any receipt type."""

        try:
            # 1. Validate file and show progress
            self._show_processing_start(file_path)

            # 2. Process through entire pipeline
            result = await self.processor.process_receipt(
                file_path=file_path,
                business_context=self._get_business_context(business_context),
                dry_run=dry_run
            )

            # 3. Handle review mode for low confidence items
            if review_mode and result.requires_review:
                result = await self._interactive_review(result)

            # 4. Format and display results
            output = self.formatter.format_processing_result(
                result,
                format_type=output_format,
                explain=explain
            )

            self._display_output(output)

            # 5. Show next steps and recommendations
            self._show_recommendations(result)

        except Exception as e:
            self._handle_error(e, file_path)

    async def _interactive_review(
        self,
        result: ProcessingResult
    ) -> ProcessingResult:
        """Interactive review for low-confidence categorizations."""

        print("\\n🔍 The following items need your review:\\n")

        for item in result.flagged_items:
            print(f"Description: {item.description}")
            print(f"Amount: ${item.amount}")
            print(f"AI Suggestion: {item.suggested_category} ({item.confidence_score:.0%} confidence)")

            # Show available categories
            categories = self._get_available_categories()
            self._show_category_options(categories)

            # Get user input
            choice = self._get_user_choice(categories, item.suggested_category)

            # Update categorization
            if choice != item.suggested_category:
                result = self._update_categorization(result, item, choice)

        return result

class OutputFormatter:
    """Rich output formatting for processing results."""

    def format_processing_result(
        self,
        result: ProcessingResult,
        format_type: str = "human",
        explain: bool = False
    ) -> str:
        """Format processing results for display."""

        if format_type == "json":
            return self._format_json(result)
        elif format_type == "csv":
            return self._format_csv(result)
        else:
            return self._format_human_readable(result, explain)

    def _format_human_readable(
        self,
        result: ProcessingResult,
        explain: bool = False
    ) -> str:
        """Format results for human consumption."""

        output = []

        # Header with file info
        output.append(f"\\n📄 Processing Results: {result.original_filename}")
        output.append(f"Vendor: {result.vendor_name}")
        output.append(f"Date: {result.transaction_date}")
        output.append(f"Total: ${result.total_amount:.2f} {result.currency}")

        # Line item breakdown
        output.append("\\n📋 Expense Breakdown:")
        output.append("-" * 60)

        for item in result.categorized_items:
            deductible_amt = item.amount * (item.deductibility_percentage / 100)

            output.append(f"{item.description:<30} ${item.amount:>8.2f}")
            output.append(f"  → {item.category} ({item.deductibility_percentage}% deductible)")
            output.append(f"  → Deductible amount: ${deductible_amt:.2f}")

            if explain:
                output.append(f"  → Applied rule: {item.applied_rule}")
                output.append(f"  → Confidence: {item.confidence_score:.0%}")

            output.append("")

        # Tax summary
        output.append("💰 Tax Summary:")
        output.append(f"Total Amount: ${result.tax_summary.total_amount:.2f}")
        output.append(f"Total Deductible: ${result.tax_summary.total_deductible:.2f}")
        output.append(f"GST/HST ITC: ${result.tax_summary.gst_itc_claimable:.2f}")

        if result.tax_summary.meals_subject_to_limitation > 0:
            output.append(f"Meals (50% limit): ${result.tax_summary.meals_deductible:.2f}")

        # QuickBooks integration
        if result.quickbooks_entries:
            output.append("\\n📊 QuickBooks Entries Created:")
            for entry in result.quickbooks_entries:
                output.append(f"  • {entry.account}: ${entry.amount:.2f} (ID: {entry.entry_id})")

        # Recommendations and warnings
        if result.recommendations:
            output.append("\\n💡 Recommendations:")
            for rec in result.recommendations:
                output.append(f"  • {rec}")

        if result.warnings:
            output.append("\\n⚠️  Warnings:")
            for warning in result.warnings:
                output.append(f"  • {warning}")

        return "\\n".join(output)
```

### Enhanced API Endpoints
```python
@router.post("/receipts/process")
async def process_receipt_universal(
    request: UniversalReceiptRequest,
    service: ExpenseProcessorDep
) -> UniversalReceiptResponse:
    """Universal receipt processing endpoint."""

    try:
        # Process through entire pipeline
        result = await service.process_receipt_universal(
            file_base64=request.file_base64,
            file_type=request.file_type,
            business_context=request.business_context,
            processing_options=request.processing_options,
            dry_run=request.dry_run
        )

        return UniversalReceiptResponse(
            success=True,
            processing_result=result,
            processing_time=result.processing_time,
            recommendations=result.recommendations
        )

    except Exception as e:
        logger.error(f"Universal processing failed: {e}")
        return UniversalReceiptResponse(
            success=False,
            error=str(e),
            error_code="PROCESSING_FAILED"
        )

@router.post("/receipts/batch")
async def process_receipts_batch(
    request: BatchReceiptRequest,
    service: ExpenseProcessorDep
) -> BatchReceiptResponse:
    """Batch receipt processing endpoint."""

    results = []

    for file_data in request.files:
        try:
            result = await service.process_receipt_universal(
                file_base64=file_data.file_base64,
                file_type=file_data.file_type,
                business_context=request.business_context,
                processing_options=request.processing_options,
                dry_run=request.dry_run
            )
            results.append(result)

        except Exception as e:
            results.append(ProcessingResult(
                success=False,
                error=str(e),
                filename=file_data.filename
            ))

    return BatchReceiptResponse(
        results=results,
        total_processed=len(results),
        total_successful=sum(1 for r in results if r.success),
        processing_time=sum(r.processing_time for r in results if r.success)
    )
```

### Models
```python
class UniversalReceiptRequest(BaseModel):
    """Universal receipt processing request."""
    file_base64: str
    file_type: str | None = None
    business_context: BusinessContext | None = None
    processing_options: ProcessingOptions | None = None
    dry_run: bool = False
    output_format: str = "detailed"

class ProcessingResult(BaseModel):
    """Comprehensive processing result."""
    success: bool
    original_filename: str
    vendor_name: str
    transaction_date: date
    total_amount: Decimal
    currency: str
    categorized_items: list[CategorizedLineItem]
    tax_summary: TaxSummary
    quickbooks_entries: list[QBSubmissionResult] | None = None
    processing_time: float
    confidence_score: float
    requires_review: bool
    flagged_items: list[CategorizedLineItem] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    audit_trail: dict[str, Any] = Field(default_factory=dict)

class UniversalReceiptResponse(BaseModel):
    """Universal receipt processing response."""
    success: bool
    processing_result: ProcessingResult | None = None
    error: str | None = None
    error_code: str | None = None
    processing_time: float | None = None
    recommendations: list[str] = Field(default_factory=list)
```

## Testing Requirements

### Unit Tests
- [ ] Universal upload command tests with different file types
- [ ] Output formatting tests for different formats (human, JSON, CSV)
- [ ] Interactive review mode functionality tests
- [ ] API endpoint tests with various input scenarios
- [ ] Batch processing tests with mixed success/failure scenarios
- [ ] Error handling and user guidance tests

### Integration Tests
- [ ] End-to-end CLI workflow with Marriott hotel bill
- [ ] API integration tests with real file uploads
- [ ] Batch processing with multiple receipt types
- [ ] Review mode with low-confidence categorizations
- [ ] Output format consistency across CLI and API
- [ ] Performance tests with large files and batches

### User Experience Tests
```python
# CLI User Experience Test Scenarios
CLI_TEST_SCENARIOS = {
    "simple_upload": {
        "command": "quickexpense upload receipt.pdf",
        "expected_output": "Processing Results with categorization breakdown"
    },
    "dry_run": {
        "command": "quickexpense upload receipt.pdf --dry-run",
        "expected_output": "Preview without QB submission"
    },
    "review_mode": {
        "command": "quickexpense upload receipt.pdf --review",
        "expected_output": "Interactive review for low-confidence items"
    },
    "json_output": {
        "command": "quickexpense upload receipt.pdf --output json",
        "expected_output": "Valid JSON response with all processing data"
    }
}
```

## Dependencies
- **PRE-106 through PRE-112:** All previous tickets for complete functionality
- Enhanced file processing, business rules, expense processor, QB integration

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] Single command handles all receipt types seamlessly
- [ ] Rich output provides actionable business insights
- [ ] API endpoints support both single and batch processing
- [ ] Interactive features enhance user experience
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate end-to-end workflows
- [ ] Performance meets requirements (<5 seconds for typical receipts)
- [ ] User documentation includes examples and best practices
- [ ] Code review completed and approved

## Validation Scenarios

### Scenario 1: First-Time User Experience
**Given** a new user with default configuration
**When** they run `quickexpense upload marriott_bill.pdf`
**Then**
- File is processed automatically through entire pipeline
- Clear categorization breakdown is displayed
- Tax implications are explained
- QB entries are created and confirmed
- Next steps and recommendations are provided

### Scenario 2: Review Mode for Complex Receipt
**Given** a receipt with ambiguous line items
**When** processed with `--review` flag
**Then** user is prompted to review low-confidence categorizations interactively

### Scenario 3: Batch Processing Workflow
**Given** multiple receipts of different types
**When** processed through batch API endpoint
**Then** all receipts are processed appropriately with summary results

### Scenario 4: API Integration
**Given** external application integrating with API
**When** universal processing endpoint is called
**Then** comprehensive results are returned in structured format

## Risk Mitigation
- **User Experience:** Extensive testing with non-technical users
- **API Consistency:** Standardized response formats across all endpoints
- **Performance:** Optimization for both single and batch processing
- **Error Handling:** Clear, actionable error messages and recovery suggestions

## Success Metrics
- Single command successfully processes 95%+ of receipt types
- User satisfaction score >4.5/5 for CLI experience
- API response time <3 seconds for typical receipts
- <10% of receipts require manual review with default settings
- Zero data loss during processing pipeline
- Complete audit trail for all processing operations
