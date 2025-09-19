# Canadian Tax Context Reference

## Understanding Canadian Business Tax Requirements

In Canada, when you run a sole proprietorship (a business owned by one person), you need to track all business expenses for tax purposes. The government provides specific forms and rules for this.

### Entity Types and Tax Forms

**Sole Proprietorship** (Current Focus)
- **Tax Form:** T2125 (Statement of Business or Professional Activities)
- **Filing:** Part of personal tax return (T1)
- **Business Number:** Optional unless GST/HST registered

**Future Entity Support:**
- **Corporation:** T2 Corporate Income Tax Return
- **Partnership:** T5013 Partnership Information Return
- **Trust:** T3 Trust Income Tax Return

### T2125 Form Structure

The T2125 form is the official tax form that sole proprietors must file with their annual tax return. Think of it as a standardized way to report all your business income and expenses to the Canada Revenue Agency (CRA). Each type of expense has a specific line number on this form:

**Common T2125 Line Items:**
- Line 8521: Advertising
- Line 8523: Meals and entertainment (50% deductible)
- Line 8810: Office supplies and expenses
- Line 8811: Office stationery and supplies
- Line 8860: Professional fees (includes legal and accounting)
- Line 8890: Travel
- Line 9270: Total expenses
- Line 9945: Business-use-of-home expenses

These aren't arbitrary numbers; they're the official categorization system the Canadian government uses.

### Tax Treatment Rules

When we process receipts, we're essentially preparing data that will eventually flow into these specific boxes on the T2125 form. The challenge is that different expenses have different tax treatments:

**Deductibility Rules:**
- **Meals & Entertainment:** 50% deductible (ITA Section 67.1)
- **Office Supplies:** 100% deductible
- **Travel:** 100% deductible when for business purposes
- **Home Office:** Prorated based on business use percentage
- **Vehicle:** Based on business use percentage

### GST/HST and Input Tax Credits

GST (Goods and Services Tax) and HST (Harmonized Sales Tax) add another layer of complexity. These are consumption taxes that businesses collect and remit to the government. However, businesses can claim back the GST/HST they pay on business expenses through something called Input Tax Credits (ITCs).

**GST/HST Registration Requirements:**
- **Mandatory:** If revenue exceeds $30,000 in any four consecutive quarters
- **GST Number Format:** 123456789RT0001 (9 digits + RT + 4 digits)
- **ITC Claims:** Require valid GST registration number from vendor

### Provincial Variations

**Tax Rates by Province (2025):**
- **GST Only (5%):** AB, NT, NU, YT
- **HST:** ON (13%), NS/NB/PE/NL (15%)
- **GST + PST:** BC (5% + 7%), SK/MB (5% + 6%/7%)
- **GST + QST:** QC (5% + 9.975%)

### Compliance References

**Key Legislation:**
- Income Tax Act (ITA)
- Excise Tax Act (GST/HST)
- Provincial tax acts

**Important Sections:**
- ITA Section 67.1: Meals and entertainment limitation
- ITA Section 18(12): Home office restrictions
- ITA Section 9: Business income calculation

### Record Keeping Requirements

**CRA Requirements:**
- Keep all receipts and supporting documents
- Maintain records for 7 years
- Electronic records acceptable if complete and accessible
- Must be able to produce audit trail

## System Implementation Notes

Our system uses this tax context to:
1. Map expenses to correct T2125 line items
2. Apply appropriate deductibility percentages
3. Calculate Input Tax Credits
4. Ensure compliance with CRA requirements
5. Provide audit-ready documentation

As we expand to support other entity types, we'll add their specific form mappings and rules while maintaining the same intelligent processing approach.
