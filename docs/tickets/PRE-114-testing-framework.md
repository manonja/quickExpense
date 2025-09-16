# PRE-114: Comprehensive Testing Framework

**Type:** Story
**Priority:** Low
**Effort:** 3 Story Points
**Sprint:** User Experience Layer

## User Story
**As a** development team
**I want** comprehensive automated testing that validates the entire multi-category expense processing system
**So that** we can confidently deploy changes and maintain high quality across all business scenarios

## Business Value
- **Problem:** Complex multi-category processing system requires extensive validation across many scenarios
- **Impact:** Risk of regressions, data accuracy issues, and compliance failures in production
- **Solution:** Comprehensive test framework covering all components with real-world business scenarios

## Description
Create a comprehensive testing framework that validates the entire expense processing pipeline from file upload through QuickBooks integration. The framework should include unit tests, integration tests, end-to-end scenarios, and performance benchmarks with particular focus on multi-category receipts like hotel bills.

## Acceptance Criteria

### AC1: Comprehensive Test Coverage
- [ ] Unit tests for all services, models, and utilities with >95% coverage
- [ ] Integration tests for component interactions and data flow
- [ ] End-to-end tests for complete processing pipelines
- [ ] Performance tests for file processing and rule application
- [ ] Regression tests for known issues and edge cases
- [ ] Contract tests for API endpoints and external integrations

### AC2: Business Scenario Validation
- [ ] Complete test suite for Marriott hotel bill processing scenario
- [ ] Tests for all common business expense types (office, meals, travel, equipment)
- [ ] Multi-category receipt processing validation
- [ ] Canadian tax compliance verification tests
- [ ] Foreign currency transaction testing
- [ ] QuickBooks integration accuracy tests

### AC3: Real-World Data Testing
- [ ] Test data library with actual receipt images and PDFs
- [ ] Anonymized real business receipts for validation
- [ ] Edge case receipts (corrupted files, unusual formats)
- [ ] Performance test data with varying file sizes
- [ ] Multi-language receipt testing capability
- [ ] Industry-specific receipt variations

### AC4: Automated Quality Gates
- [ ] Continuous integration test pipeline
- [ ] Automated test execution on code changes
- [ ] Quality metrics reporting and trend analysis
- [ ] Performance regression detection
- [ ] Test result reporting and notifications
- [ ] Coverage reporting with trend tracking

### AC5: Testing Tools and Utilities
- [ ] Test data generation utilities for receipt creation
- [ ] Mock services for external dependencies (QuickBooks, Gemini)
- [ ] Test environment management and cleanup
- [ ] Parallel test execution for faster feedback
- [ ] Test debugging and diagnostic tools
- [ ] Load testing utilities for stress testing

## Technical Implementation

### Files to Create/Enhance
- `tests/framework/` - Testing framework utilities
- `tests/data/` - Test data and fixtures
- `tests/scenarios/` - Business scenario tests
- `tests/performance/` - Performance and load tests
- `tests/integration/test_end_to_end.py` - Complete pipeline tests
- `tests/contract/` - API contract tests

### Test Framework Structure
```python
class ExpenseProcessingTestFramework:
    """Comprehensive test framework for expense processing."""

    def __init__(self):
        self.data_factory = TestDataFactory()
        self.mock_manager = MockServiceManager()
        self.performance_tracker = PerformanceTracker()
        self.validation_engine = ValidationEngine()

    async def run_business_scenario(
        self,
        scenario: BusinessScenario
    ) -> ScenarioTestResult:
        """Run complete business scenario test."""

        result = ScenarioTestResult(scenario_name=scenario.name)

        try:
            # 1. Setup test environment
            await self._setup_test_environment(scenario)

            # 2. Process receipt through entire pipeline
            processing_result = await self._process_receipt_full_pipeline(
                scenario.receipt_data
            )

            # 3. Validate against expected results
            validation_result = await self.validation_engine.validate_scenario(
                processing_result, scenario.expected_results
            )

            # 4. Verify QuickBooks integration
            qb_validation = await self._validate_quickbooks_integration(
                processing_result, scenario.expected_qb_entries
            )

            # 5. Check tax compliance
            tax_validation = await self._validate_tax_compliance(
                processing_result, scenario.tax_requirements
            )

            result.success = all([
                validation_result.success,
                qb_validation.success,
                tax_validation.success
            ])

            result.details = {
                "processing": validation_result,
                "quickbooks": qb_validation,
                "tax_compliance": tax_validation
            }

        except Exception as e:
            result.success = False
            result.error = str(e)

        finally:
            await self._cleanup_test_environment(scenario)

        return result

class TestDataFactory:
    """Factory for creating test data and fixtures."""

    def create_marriott_hotel_bill(
        self,
        variation: str = "standard"
    ) -> TestReceipt:
        """Create Marriott hotel bill test data."""

        base_data = {
            "vendor_name": "Courtyard by Marriott Edmonton",
            "transaction_date": "2025-04-24",
            "currency": "CAD",
            "line_items": [
                {
                    "description": "Room Charge",
                    "amount": 175.00,
                    "expected_category": "Travel-Lodging",
                    "expected_deductibility": 100
                },
                {
                    "description": "Restaurant Room Charge",
                    "amount": 40.70,
                    "expected_category": "Travel-Meals",
                    "expected_deductibility": 50
                },
                {
                    "description": "Tourism Levy",
                    "amount": 7.21,
                    "expected_category": "Travel-Lodging",
                    "expected_deductibility": 100
                },
                {
                    "description": "GST",
                    "amount": 9.01,
                    "expected_category": "Tax-GST",
                    "expected_deductibility": 100
                }
            ]
        }

        # Apply variations
        if variation == "multi_night":
            base_data["line_items"].extend([
                {
                    "description": "Room Charge - Night 2",
                    "amount": 175.00,
                    "expected_category": "Travel-Lodging",
                    "expected_deductibility": 100
                }
            ])

        return TestReceipt(**base_data)

    def create_office_supply_receipt(self) -> TestReceipt:
        """Create office supply receipt test data."""

        return TestReceipt(
            vendor_name="Staples",
            transaction_date="2025-01-15",
            currency="CAD",
            line_items=[
                {
                    "description": "Copy Paper - 5 Reams",
                    "amount": 45.99,
                    "expected_category": "Office Supplies",
                    "expected_deductibility": 100
                },
                {
                    "description": "Ink Cartridge",
                    "amount": 67.50,
                    "expected_category": "Office Supplies",
                    "expected_deductibility": 100
                },
                {
                    "description": "GST",
                    "amount": 5.67,
                    "expected_category": "Tax-GST",
                    "expected_deductibility": 100
                }
            ]
        )

class BusinessScenario(BaseModel):
    """Complete business scenario for testing."""
    name: str
    description: str
    receipt_data: TestReceipt
    business_context: BusinessContext
    expected_results: ExpectedResults
    expected_qb_entries: list[ExpectedQBEntry]
    tax_requirements: TaxComplianceRequirements
    performance_requirements: PerformanceRequirements | None = None

class ValidationEngine:
    """Validates processing results against expectations."""

    async def validate_scenario(
        self,
        actual: ProcessingResult,
        expected: ExpectedResults
    ) -> ValidationResult:
        """Validate complete scenario results."""

        validation = ValidationResult()

        # Validate categorization accuracy
        categorization_accuracy = self._validate_categorization(
            actual.categorized_items,
            expected.categorized_items
        )
        validation.categorization_accuracy = categorization_accuracy

        # Validate tax calculations
        tax_accuracy = self._validate_tax_calculations(
            actual.tax_summary,
            expected.tax_summary
        )
        validation.tax_accuracy = tax_accuracy

        # Validate deductibility calculations
        deductibility_accuracy = self._validate_deductibility(
            actual.categorized_items,
            expected.deductible_amounts
        )
        validation.deductibility_accuracy = deductibility_accuracy

        # Overall success
        validation.success = all([
            categorization_accuracy >= 0.95,
            tax_accuracy >= 0.99,
            deductibility_accuracy >= 0.99
        ])

        return validation
```

### Test Scenarios Definition
```python
# Comprehensive test scenarios
TEST_SCENARIOS = {
    "marriott_hotel_standard": BusinessScenario(
        name="Marriott Hotel Bill - Standard",
        description="Standard 2-night hotel stay with meals and taxes",
        receipt_data=TestDataFactory().create_marriott_hotel_bill(),
        business_context=BusinessContext(
            business_type="consulting",
            tax_jurisdiction="Canada"
        ),
        expected_results=ExpectedResults(
            total_categories=3,  # Lodging, Meals, GST
            total_deductible=Decimal("211.56"),
            categories_expected=["Travel-Lodging", "Travel-Meals", "Tax-GST"]
        ),
        expected_qb_entries=[
            ExpectedQBEntry(
                account="Travel - Lodging",
                amount=Decimal("182.21"),
                memo_contains="100% deductible"
            ),
            ExpectedQBEntry(
                account="Travel - Meals & Entertainment",
                amount=Decimal("40.70"),
                memo_contains="50% deductible"
            ),
            ExpectedQBEntry(
                account="GST/HST Paid on Purchases",
                amount=Decimal("9.01"),
                memo_contains="Input Tax Credit"
            )
        ],
        tax_requirements=TaxComplianceRequirements(
            cra_compliant=True,
            meal_limitation_applied=True,
            gst_itc_eligible=True
        )
    ),

    "complex_multi_category": BusinessScenario(
        name="Complex Multi-Category Receipt",
        description="Receipt with office supplies, equipment, and professional services",
        # ... detailed scenario definition
    ),

    "foreign_currency": BusinessScenario(
        name="Foreign Currency Transaction",
        description="CAD receipt paid with USD credit card",
        # ... detailed scenario definition
    )
}
```

### Performance Testing
```python
class PerformanceTestSuite:
    """Performance testing for expense processing."""

    async def test_file_processing_performance(self):
        """Test file processing performance across different sizes."""

        test_files = [
            {"size": "small", "file": "receipt_100kb.pdf", "max_time": 2.0},
            {"size": "medium", "file": "receipt_1mb.pdf", "max_time": 5.0},
            {"size": "large", "file": "receipt_5mb.pdf", "max_time": 10.0}
        ]

        for test_file in test_files:
            start_time = time.time()

            result = await self.processor.process_file(test_file["file"])

            processing_time = time.time() - start_time

            assert processing_time < test_file["max_time"], (
                f"Processing took {processing_time:.2f}s, "
                f"expected < {test_file['max_time']}s"
            )

    async def test_rule_engine_performance(self):
        """Test rule engine performance with large rule sets."""

        # Test with 100+ rules and complex receipts
        large_rule_set = self._generate_large_rule_set(100)
        complex_receipt = self._generate_complex_receipt(50)  # 50 line items

        start_time = time.time()

        result = await self.rule_engine.apply_rules(
            complex_receipt, large_rule_set
        )

        processing_time = time.time() - start_time

        # Should process 50 line items with 100 rules in < 1 second
        assert processing_time < 1.0
```

## Testing Requirements

### Core Test Coverage
- [ ] Unit tests: >95% code coverage across all modules
- [ ] Integration tests: All service interactions and data flow
- [ ] End-to-end tests: Complete processing pipelines
- [ ] Contract tests: API endpoint specifications
- [ ] Performance tests: Response time and throughput requirements
- [ ] Security tests: Input validation and error handling

### Business Scenario Coverage
- [ ] Hotel bill processing (primary use case)
- [ ] Restaurant receipts with meal limitations
- [ ] Office supply receipts
- [ ] Equipment purchases (capital vs expense)
- [ ] Professional services receipts
- [ ] Multi-category receipts with complex categorization

### Edge Case Coverage
- [ ] Corrupted or invalid files
- [ ] Extremely large receipts (100+ line items)
- [ ] Foreign currency transactions
- [ ] Zero-amount line items
- [ ] Ambiguous categorization scenarios
- [ ] QuickBooks API failures and retries

## Dependencies
- **All previous tickets (PRE-106 through PRE-113)** - Complete system required for testing
- Test data creation and management utilities
- Mock service implementations

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] >95% test coverage across entire codebase
- [ ] All business scenarios pass validation tests
- [ ] Performance tests meet response time requirements
- [ ] Continuous integration pipeline implemented
- [ ] Test documentation and maintenance guide completed
- [ ] Mock services available for isolated testing
- [ ] Real-world test data library established
- [ ] Code review completed and approved

## Validation Scenarios

### Scenario 1: Complete System Validation
**Given** the entire expense processing system
**When** comprehensive test suite is executed
**Then** all components pass validation with >95% accuracy

### Scenario 2: Marriott Hotel Bill End-to-End
**Given** a Marriott hotel bill PDF
**When** processed through complete pipeline
**Then**
- PDF converts to image correctly
- AI extracts all line items accurately
- Business rules categorize items properly
- Tax calculations are CRA-compliant
- QuickBooks entries are created correctly

### Scenario 3: Performance Under Load
**Given** multiple concurrent receipt processing requests
**When** load testing is performed
**Then** system maintains response times and accuracy under load

### Scenario 4: Regression Prevention
**Given** new code changes
**When** regression test suite runs
**Then** no existing functionality is broken

## Risk Mitigation
- **Test Data Management:** Automated test data generation and cleanup
- **External Dependencies:** Comprehensive mocking for reliability
- **Performance Regression:** Automated performance monitoring
- **Test Maintenance:** Clear documentation and update procedures

## Success Metrics
- Test suite runs in <10 minutes for full validation
- >95% test coverage maintained across all modules
- Zero false positives in business scenario validation
- Performance tests detect regressions within 5% threshold
- Test suite provides clear diagnostic information for failures
- New features require corresponding test coverage before merge
