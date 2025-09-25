# PRE-116: Provincial Tax Rate Management for All Canada

**Type:** Enhancement
**Priority:** High (Tax Compliance Foundation)
**Effort:** 2 Story Points
**Sprint:** Phase 1 - Enhanced User Experience

## User Story
**As a** BC-based sole proprietor traveling across Canada for business
**I want** the system to correctly handle receipts from any Canadian province
**So that** my tax calculations are accurate regardless of where I conducted business

## Business Value
- **Problem:** Current system handles GST/HST generically without provincial-specific variations
- **Impact:** Incorrect Input Tax Credit calculations, potential CRA compliance issues
- **Solution:** Comprehensive provincial tax rate management with auto-detection

## Description
Implement a provincial tax service that correctly handles all Canadian provincial tax variations including GST, HST, PST, and QST. The system should auto-detect the province from receipt data and apply the correct tax rates and Input Tax Credit calculations.

## Provincial Tax Landscape
**Current Rates (2025):**
- **BC:** 5% GST + 7% PST (12% total)
- **AB:** 5% GST only
- **SK:** 5% GST + 6% PST (11% total)
- **MB:** 5% GST + 7% PST (12% total)
- **ON:** 13% HST
- **QC:** 5% GST + 9.975% QST (14.975% total)
- **NB:** 15% HST
- **NS:** 15% HST
- **PE:** 15% HST
- **NL:** 15% HST
- **YT:** 5% GST only
- **NT:** 5% GST only
- **NU:** 5% GST only

## Acceptance Criteria

### AC1: Provincial Tax Rate Service
- [ ] Create ProvincialTaxService with comprehensive rate data
- [ ] Support GST, HST, PST, and QST calculations
- [ ] Include effective date tracking for rate changes
- [ ] Validate tax amounts against expected provincial rates
- [ ] Calculate correct Input Tax Credits by province

### AC2: Province Auto-Detection
- [ ] Detect province from vendor address information
- [ ] Parse common address formats and postal codes
- [ ] Fallback to user-configured default province (BC)
- [ ] Handle edge cases (national chains, unclear addresses)
- [ ] Log province detection decisions for audit

### AC3: T2125 Form Integration for Sole Proprietors
- [ ] Map expense categories to T2125 line items
- [ ] Implement T2125LineItem enum with official line numbers
- [ ] Validate categorization against CRA T2125 requirements
- [ ] Support entity-aware form mapping (extensible for future T2, T5013)
- [ ] Include T2125 line numbers in CLI output and audit trail

### AC4: Enhanced Business Rules Integration
- [ ] Extend business rules to consider provincial context
- [ ] Apply province-specific tax treatments
- [ ] Update confidence scoring with provincial alignment
- [ ] Validate rule applications against provincial regulations

### AC5: QuickBooks Integration Enhancement
- [ ] Create appropriate tax accounts by province
- [ ] Map GST/HST/PST to correct QuickBooks accounts
- [ ] Handle Input Tax Credit entries properly
- [ ] Support provincial tax reporting requirements

### AC6: CLI Output Enhancement
- [ ] Display provincial tax breakdown in receipt output
- [ ] Show Input Tax Credits by tax type
- [ ] Include province detection confidence
- [ ] Provide provincial tax compliance notes

## Technical Implementation

### Files to Create/Modify
- `src/quickexpense/services/provincial_tax.py` - New provincial tax service
- `src/quickexpense/services/business_rules.py` - Enhance with provincial context
- `src/quickexpense/models/tax.py` - Tax models and calculations
- `src/quickexpense/models/t2125.py` - T2125 form models and line items
- `src/quickexpense/cli.py` - Enhanced output formatting
- `tests/services/test_provincial_tax.py` - Comprehensive tests

### ProvincialTaxService
```python
class T2125LineItem(str, Enum):
    """Official T2125 form line items for sole proprietors."""

    # Income lines (not used for expenses but included for completeness)
    GROSS_SALES = "8000"

    # Expense lines
    ADVERTISING = "8521"
    MEALS_ENTERTAINMENT = "8523"  # 50% deductible
    BAD_DEBTS = "8590"
    INTEREST = "8710"
    BUSINESS_TAX = "8760"
    LICENCES = "8764"
    OFFICE_SUPPLIES = "8811"
    PROFESSIONAL_FEES = "8860"
    MANAGEMENT_FEES = "8871"
    RENT = "8910"
    MAINTENANCE = "8960"
    SALARIES_WAGES = "9060"
    SUBCONTRACTS = "9180"
    TRAVEL = "8890"
    TELEPHONE = "9220"
    UTILITIES = "9270"
    VEHICLE_EXPENSES = "9281"
    HOME_OFFICE = "9945"
    OTHER_EXPENSES = "9999"

    @property
    def description(self) -> str:
        """Get human-readable description of line item."""
        descriptions = {
            "8521": "Advertising",
            "8523": "Meals and entertainment (50% deductible)",
            "8590": "Bad debts",
            "8710": "Interest",
            "8760": "Business tax, fees, licences",
            "8764": "Licences",
            "8811": "Office expenses",
            "8860": "Professional fees",
            "8871": "Management and administration fees",
            "8910": "Rent",
            "8960": "Maintenance and repairs",
            "9060": "Salaries, wages, and benefits",
            "9180": "Subcontracts",
            "8890": "Travel",
            "9220": "Telephone and utilities",
            "9270": "Utilities",
            "9281": "Motor vehicle expenses",
            "9945": "Business-use-of-home expenses",
            "9999": "Other expenses"
        }
        return descriptions.get(self.value, self.value)

class ProvincialTaxService:
    """Handle provincial tax rates across Canada."""

    PROVINCIAL_RATES = {
        "BC": {
            "gst_rate": Decimal("0.05"),
            "pst_rate": Decimal("0.07"),
            "combined_rate": Decimal("0.12"),
            "tax_type": "GST+PST",
            "itc_eligible": {"gst": True, "pst": False}
        },
        "AB": {
            "gst_rate": Decimal("0.05"),
            "combined_rate": Decimal("0.05"),
            "tax_type": "GST",
            "itc_eligible": {"gst": True}
        },
        "ON": {
            "hst_rate": Decimal("0.13"),
            "combined_rate": Decimal("0.13"),
            "tax_type": "HST",
            "itc_eligible": {"hst": True}
        },
        "QC": {
            "gst_rate": Decimal("0.05"),
            "qst_rate": Decimal("0.09975"),
            "combined_rate": Decimal("0.14975"),
            "tax_type": "GST+QST",
            "itc_eligible": {"gst": True, "qst": True}
        }
        # ... all provinces
    }

    def detect_province(self, vendor_address: str, postal_code: str | None = None) -> ProvinceDetection:
        """Auto-detect province from address information."""

    def calculate_tax_breakdown(self, total_amount: Decimal, tax_amount: Decimal, province: str) -> TaxBreakdown:
        """Calculate detailed tax breakdown by province."""

    def calculate_input_tax_credits(self, tax_breakdown: TaxBreakdown) -> InputTaxCredits:
        """Calculate ITC amounts based on provincial rules."""
```

### Enhanced Models
```python
class ProvinceDetection(BaseModel):
    """Province detection result."""
    province: str
    confidence: float
    detection_method: str  # "address", "postal_code", "default"
    vendor_address: str | None = None

class TaxBreakdown(BaseModel):
    """Detailed provincial tax breakdown."""
    province: str
    total_amount: Decimal
    tax_amount: Decimal
    gst_amount: Decimal = Decimal("0")
    pst_amount: Decimal = Decimal("0")
    hst_amount: Decimal = Decimal("0")
    qst_amount: Decimal = Decimal("0")

class EntityAwareExpenseMapping(BaseModel):
    """Entity-aware expense mapping to tax forms."""

    entity_type: str
    expense_category: str
    form_line_item: str
    deductibility_percentage: float
    description: str

    @classmethod
    def get_mapping(cls, entity_type: str, category: str) -> 'EntityAwareExpenseMapping':
        """Get expense mapping based on entity type."""

        # Sole proprietorship mappings (T2125)
        if entity_type == "sole_proprietorship":
            mappings = {
                "Travel-Meals": cls(
                    entity_type="sole_proprietorship",
                    expense_category="Travel-Meals",
                    form_line_item=T2125LineItem.MEALS_ENTERTAINMENT,
                    deductibility_percentage=50.0,
                    description="Meals and entertainment (50% deductible per ITA 67.1)"
                ),
                "Travel-Lodging": cls(
                    entity_type="sole_proprietorship",
                    expense_category="Travel-Lodging",
                    form_line_item=T2125LineItem.TRAVEL,
                    deductibility_percentage=100.0,
                    description="Travel expenses (100% deductible)"
                ),
                "Office-Supplies": cls(
                    entity_type="sole_proprietorship",
                    expense_category="Office-Supplies",
                    form_line_item=T2125LineItem.OFFICE_SUPPLIES,
                    deductibility_percentage=100.0,
                    description="Office supplies and expenses"
                ),
                "Professional-Services": cls(
                    entity_type="sole_proprietorship",
                    expense_category="Professional-Services",
                    form_line_item=T2125LineItem.PROFESSIONAL_FEES,
                    deductibility_percentage=100.0,
                    description="Professional fees (legal, accounting, consulting)"
                )
            }
            return mappings.get(category, cls(
                entity_type="sole_proprietorship",
                expense_category=category,
                form_line_item=T2125LineItem.OTHER_EXPENSES,
                deductibility_percentage=100.0,
                description="Other business expenses"
            ))

        # Future: Corporation mappings (T2), Partnership mappings (T5013)
        else:
            raise ValueError(f"Entity type '{entity_type}' not yet supported")

class InputTaxCredits(BaseModel):
    """Input Tax Credit calculations."""
    total_itc: Decimal
    gst_itc: Decimal = Decimal("0")
    hst_itc: Decimal = Decimal("0")
    qst_itc: Decimal = Decimal("0")
    pst_itc: Decimal = Decimal("0")  # Usually 0 except special cases
```

## Testing Requirements

### Unit Tests
- [ ] Test all provincial tax rate calculations
- [ ] Test province detection from various address formats
- [ ] Test Input Tax Credit calculations
- [ ] Test edge cases (territories, invalid provinces)
- [ ] Test postal code parsing and validation

### Integration Tests
- [ ] Test with real receipts from different provinces
- [ ] Validate QuickBooks account mapping
- [ ] Test business rules integration with provincial context
- [ ] Performance tests with batch provincial processing

### Test Scenarios
```python
# Provincial Tax Calculation Tests
PROVINCIAL_TEST_CASES = {
    "bc_restaurant": {
        "province": "BC",
        "total": Decimal("50.00"),
        "tax": Decimal("6.00"),  # 12% HST equivalent
        "expected_gst": Decimal("2.38"),  # 5% of base
        "expected_pst": Decimal("3.33"),  # 7% of base
        "expected_itc": Decimal("2.38")   # GST only
    },
    "ontario_hotel": {
        "province": "ON",
        "total": Decimal("200.00"),
        "tax": Decimal("23.01"),  # 13% HST
        "expected_hst": Decimal("23.01"),
        "expected_itc": Decimal("23.01")  # Full HST
    },
    "quebec_meal": {
        "province": "QC",
        "total": Decimal("75.00"),
        "tax": Decimal("10.23"),  # GST + QST
        "expected_gst": Decimal("3.57"),  # 5% of base
        "expected_qst": Decimal("6.66"),  # 9.975% of base
        "expected_itc": Decimal("10.23")  # Both eligible
    }
}
```

## Dependencies
- Existing business rules engine (PRE-107) ✅ Completed
- QuickBooks integration (PRE-110) ✅ Completed
- Enhanced models (PRE-106) ✅ Completed

## Definition of Done
- [ ] All Canadian provinces and territories supported
- [ ] Auto-detection of province from receipt data
- [ ] Correct Input Tax Credit calculations by province
- [ ] Enhanced CLI output with provincial tax details
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate real-world scenarios
- [ ] Pre-commit hooks pass (ruff, mypy, pyright, black)
- [ ] Real receipt testing across multiple provinces

## Validation Scenarios

### Scenario 1: BC Sole Proprietor Travel to Alberta
**Given** BC sole proprietor with Alberta gas station receipt
**When** receipt processed with vendor address in Calgary, AB
**Then**
- Entity type: sole_proprietorship
- Province detected as Alberta (confidence >90%)
- 5% GST calculated correctly
- No PST applied
- T2125 line item: 9281 (Motor vehicle expenses)
- Input Tax Credit = full GST amount
- CLI shows "Alberta (5% GST only) → T2125 Line 9281"

### Scenario 2: Cross-Country Business Trip (T2125 Mapping)
**Given** sole proprietor receipts from BC, AB, ON, QC in single batch
**When** batch processed with provincial detection
**Then**
- Each receipt processed with correct provincial rates
- T2125 line items mapped correctly:
  * Hotel: Line 8890 (Travel)
  * Meals: Line 8523 (Meals & entertainment, 50%)
  * Gas: Line 9281 (Motor vehicle expenses)
- Summary shows tax breakdown by province
- Total ITC calculated correctly across provinces
- CLI output includes T2125 line numbers for CRA filing

### Scenario 3: Quebec Business Meeting (Entity-Aware)
**Given** sole proprietor restaurant receipt from Montreal, QC
**When** processed with detected QC province
**Then**
- Entity type: sole_proprietorship (T2125 form)
- 5% GST + 9.975% QST calculated separately
- Both GST and QST eligible for ITC
- T2125 line item: 8523 (Meals & entertainment)
- Deductibility: 50% per ITA Section 67.1
- CLI shows: "Quebec (GST + QST) → T2125 Line 8523 (50% deductible)"
- Compliance note references meals limitation

## Risk Mitigation
- **Complex Tax Rules:** Start with major provinces, expand gradually
- **Address Parsing:** Multiple detection methods with fallbacks
- **Rate Changes:** Date-based rate management for future updates
- **Edge Cases:** Comprehensive testing with real receipt data

## Success Metrics
- 100% accurate provincial tax detection for major provinces
- Zero Input Tax Credit calculation errors
- Provincial context improves business rule confidence by >10%
- User feedback confirms cross-Canada receipt processing accuracy
