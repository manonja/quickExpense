# Business Rules Testing Guide

## Overview

The QuickExpense CLI now includes an integrated **Business Rules Engine** that automatically categorizes receipt line items according to Canadian tax compliance rules (CRA Section 67.1). This guide shows you how to test the complete workflow using a Marriott hotel PDF receipt.

## Features Implemented

✅ **AI-Powered Receipt Extraction** (Gemini AI)
✅ **Business Rules Engine** (12 Canadian tax compliance rules)
✅ **PDF Processing** (PyMuPDF conversion)
✅ **Multi-Category Expense Support**
✅ **Tax Deductibility Calculations**
✅ **Enhanced CLI Output** with business rules details

## Prerequisites

1. **Environment Setup**:
   ```bash
   # Set Gemini AI API key
   export GEMINI_API_KEY="your_gemini_api_key"

   # Optional: QuickBooks authentication (for actual expense creation)
   uv run quickexpense auth
   ```

2. **Verify System Status**:
   ```bash
   uv run quickexpense status
   ```

   Expected output should show:
   - ✅ **Gemini AI**: API key configured
   - ✅ **Business Rules**: Loaded (12 rules)
   - ✅ **Configuration**: Valid

## Test Commands

### 1. Test with Marriott PDF (Dry Run)

Test the complete workflow without creating expenses in QuickBooks:

```bash
uv run quickexpense upload /Users/manonjacquin/Documents/receipts/marriot.pdf --dry-run
```

**Expected Output**:
```
Extracting data from receipt: marriot.pdf
Applying business rules for categorization...

=== DRY RUN MODE ===

=== Receipt Data ===
File: /Users/manonjacquin/Documents/receipts/marriot.pdf
Vendor: Courtyard by Marriott
Date: 2019-12-20
Total Amount: $237.17
Tax: $9.01
Currency: CAD

=== Business Rules Categorization ===

📄 Room Charge
   Rule Applied: Hotel Accommodation Charges
   Category: Travel-Lodging
   QuickBooks Account: Travel - Lodging
   Tax Deductible: 100%
   Tax Treatment: standard
   Confidence: 100.0%
   ✅ Matched Rule

📄 Restaurant Room Charge
   Rule Applied: Hotel Room Service Meals
   Category: Travel-Meals
   QuickBooks Account: Travel - Meals & Entertainment
   Tax Deductible: 50%
   Tax Treatment: meals_limitation
   Confidence: 95.0%
   ✅ Matched Rule

📄 Marketing Fee
   Rule Applied: Marketing and Service Fees
   Category: Professional Services
   QuickBooks Account: Professional Fees
   Tax Deductible: 100%
   Tax Treatment: standard
   Confidence: 85.0%
   ✅ Matched Rule

📄 GST 767657513
   Rule Applied: GST/HST Tax Charges
   Category: Tax-GST/HST
   QuickBooks Account: GST/HST Paid on Purchases
   Tax Deductible: 100%
   Tax Treatment: input_tax_credit
   Confidence: 100.0%
   ✅ Matched Rule

📄 Tourism Levy
   Rule Applied: Tourism Levy and Municipal Taxes
   Category: Travel-Taxes
   QuickBooks Account: Travel - Other
   Tax Deductible: 100%
   Tax Treatment: standard
   Confidence: 90.0%
   ✅ Matched Rule

=== Tax Deductibility Summary ===
Total Amount: $237.17
Deductible Amount: $216.82 (91.4%)

Deductible by Category:
  • Travel-Lodging: $175.00
  • Travel-Meals: $20.35
  • Professional Services: $5.25
  • Tax-GST/HST: $9.01
  • Travel-Taxes: $7.21

=== Enhanced Expense Summary ===
Vendor: Courtyard by Marriott
Categories: 5 items across 5 categories
Business Rules Applied: 5
Payment Method: credit_card

=== Result ===
DRY RUN - No expense created in QuickBooks
```

### 2. Test with JSON Output

Get detailed JSON output for API integration or debugging:

```bash
uv run quickexpense upload /Users/manonjacquin/Documents/receipts/marriot.pdf --dry-run --output json
```

This returns structured JSON with:
- `receipt`: Raw Gemini AI extraction results
- `enhanced_expense`: Multi-category expense with business rules applied
- `business_rules`: Detailed rule applications and deductibility calculations

### 3. Test Business Rules Only (Without PDF)

Test just the business rules engine with simulated data:

```bash
uv run python scripts/test_business_rules_with_marriott.py
```

### 4. Create Actual QuickBooks Expense

**⚠️ Requires QuickBooks authentication and valid tokens**

```bash
# First authenticate (if not already done)
uv run quickexpense auth

# Create actual expense in QuickBooks
uv run quickexpense upload /Users/manonjacquin/Documents/receipts/marriot.pdf
```

## Expected Business Rules Results

For a typical Marriott hotel bill, the system should categorize expenses as follows:

| Line Item | Category | Deductible % | Tax Treatment | QuickBooks Account |
|-----------|----------|--------------|---------------|-------------------|
| Room Charge | Travel-Lodging | 100% | Standard | Travel - Lodging |
| Restaurant Room Charge | Travel-Meals | 50% | Meals Limitation | Travel - Meals & Entertainment |
| Marketing Fee | Professional Services | 100% | Standard | Professional Fees |
| GST/HST | Tax-GST/HST | 100% | Input Tax Credit | GST/HST Paid on Purchases |
| Tourism Levy | Travel-Taxes | 100% | Standard | Travel - Other |

**Total Deductibility**: ~91.4% (due to 50% meals limitation per CRA Section 67.1)

## Business Rules Configuration

The system uses 12 predefined Canadian tax compliance rules located in:
```
config/business_rules.json
```

Key rules include:
- **Hotel Accommodation** (Priority 100): Room charges, 100% deductible
- **Room Service Meals** (Priority 105): Restaurant charges, 50% deductible
- **GST/HST Charges** (Priority 85): Tax charges, Input Tax Credit eligible
- **Tourism Levies** (Priority 80): Municipal taxes, 100% deductible
- **Marketing Fees** (Priority 75): Service fees, 100% deductible

## Troubleshooting

### Business Rules Not Loading
```bash
# Check business rules status
uv run quickexpense status

# Expected: ✅ Business Rules: Loaded (12 rules)
```

### PDF Processing Issues
- Ensure PyMuPDF is installed: `uv sync`
- Check file exists and is readable
- Verify file format is PDF with readable content

### Gemini AI Issues
```bash
# Verify API key is set
echo $GEMINI_API_KEY

# Check status
uv run quickexpense status
# Expected: ✅ Gemini AI: API key configured
```

### QuickBooks Authentication
```bash
# Re-authenticate if tokens expired
uv run quickexpense auth --force
```

## Integration Notes

- **PDF Support**: Uses PyMuPDF for high-quality PDF-to-image conversion
- **Multi-Category Processing**: Each line item is individually categorized
- **Canadian Tax Compliance**: Implements CRA Section 67.1 (50% meals limitation)
- **Fallback Rules**: Unknown expenses are flagged for manual review
- **Audit Trail**: All rule applications are logged for compliance

## API Integration

The CLI can output structured JSON for integration with other systems:

```bash
# Get JSON output
uv run quickexpense upload receipt.pdf --output json --dry-run > result.json
```

The JSON structure includes:
- `receipt`: Gemini AI extraction results
- `enhanced_expense`: Multi-category expense data
- `business_rules`: Rule applications and tax calculations

## Next Steps

1. **Test with various receipt types** (restaurants, office supplies, fuel, etc.)
2. **Customize business rules** by editing `config/business_rules.json`
3. **Add custom rules** for specific business needs
4. **Integrate with accounting workflows** using JSON output

The business rules system is designed to be configurable and can be extended to support different jurisdictions or custom business requirements without code changes.
