# Agents vs Baseline API Test Results

**Date**: 2025-10-30
**Receipt**: Marriott Hotel Invoice (`marriot.pdf`)
**Total Amount**: $535.46 (11 line items)
**Context**: "Hotel accommodation for business conference"

---

## Test Commands

### 1. Baseline Test (Gemini + Business Rules Engine)

```bash
curl -X POST http://localhost:8000/api/web/upload-receipt \
  -F "file=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel accommodation for business conference" \
  -F "dry_run=true" \
  -s | jq '.'
```

**Summary command:**
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt \
  -F "file=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq '{method: "baseline", total: .receipt_info.total_amount, deductible: .tax_deductibility.deductible_amount, rate: .tax_deductibility.deductibility_rate, categories: [.business_rules.applied_rules[].category] | unique}'
```

### 2. Agents Test (Multi-Agent System with RAG)

```bash
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel accommodation for business conference" \
  -F "dry_run=true" \
  -s | jq '.'
```

**Summary command:**
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq '{method: "agents", total: (.receipt_info.total_amount | tonumber), deductible: .agent_details.full_agent_data.total_deductible, rate: (.agent_details.full_agent_data.deductibility_rate | tonumber), categories: [.agent_details.full_agent_data.line_items[].category] | unique, confidence: .agent_details.overall_confidence}'
```

---

## Results Comparison

| Metric | Baseline (Gemini + Rules) | Agents (Multi-Agent + RAG) |
|--------|---------------------------|----------------------------|
| **Total Amount** | $535.46 | $535.46 |
| **Deductible Amount** | $464.20 | $453.70 |
| **Deductibility Rate** | 86.7% | 84.7% |
| **Difference** | --- | -$10.50 (2% more conservative) |
| **Categories Used** | 4 categories | 5 categories |
| **Confidence** | Rule-based | 85% (AI-powered) |
| **Processing Time** | ~5-10 seconds | ~15 seconds |

---

## Key Finding: Marketing Fee Categorization

The **$10.50 difference** comes entirely from how "Marketing Fee" line items are categorized:

### Baseline Approach
```json
{
  "description": "Marketing Fee",
  "amount": 5.25,
  "category": "Travel-Lodging",
  "deductible_percentage": 100,
  "rule_applied": "hotel_marketing_fees"
}
```
- **Categorization**: Travel-Lodging
- **Deductibility**: 100% (2x $5.25 = $10.50 deductible)
- **Reasoning**: Keyword match "marketing fee" + vendor "Marriott"

### Agents Approach
```json
{
  "description": "Marketing Fee",
  "amount": 5.25,
  "category": "Uncategorized-Review-Required",
  "deductibility_percent": 0,
  "reasoning": "Marketing Fee is ambiguous and may be personal or business-related, requiring manual review"
}
```
- **Categorization**: Uncategorized-Review-Required
- **Deductibility**: 0% (2x $5.25 = $10.50 flagged for review)
- **Reasoning**: AI determines ambiguity requires human judgment

---

## Line-by-Line Breakdown

### View Baseline Line Items
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt \
  -F "file=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq -r '.business_rules.applied_rules[] | "\(.description): \(.category) (\(.deductible_percentage)%) - \(.rule_name)"'
```

**Output:**
```
Restaurant Room Charge: Travel-Meals (50%) - Hotel Room Service Meals
Room Charge: Travel-Lodging (100%) - Hotel Accommodation Charges
Marketing Fee: Travel-Lodging (100%) - Hotel Marketing and Service Fees ⚠️
Gst 767657513: Tax-GST/HST (100%) - GST/HST Tax Charges
Tourism Levy: Travel-Taxes (100%) - Tourism Levy and Municipal Taxes
Restaurant Room Charge: Travel-Meals (50%) - Hotel Room Service Meals
Restaurant Room Charge: Travel-Meals (50%) - Hotel Room Service Meals
Room Charge: Travel-Lodging (100%) - Hotel Accommodation Charges
Marketing Fee: Travel-Lodging (100%) - Hotel Marketing and Service Fees ⚠️
Gst 767657513: Tax-GST/HST (100%) - GST/HST Tax Charges
Tourism Levy: Travel-Taxes (100%) - Tourism Levy and Municipal Taxes
```

### View Agents Line Items
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq -r '.agent_details.full_agent_data.line_items[] | "\(.original_description): \(.category) (\(.deductibility_percent)%) - \(.reasoning)"'
```

**Output:**
```
Restaurant Room Charge: Travel-Meals (50%) - Restaurant Room Charge implies a meal expense, which is 50% deductible according to CRA rules (ITA Section 67.1)
Room Charge: Travel-Lodging (100%) - Room Charge is a lodging expense, which is 100% deductible according to CRA rules
Marketing Fee: Uncategorized-Review-Required (0%) - Marketing Fee is ambiguous and may be personal or business-related, requiring manual review ⭐
Gst 767657513: Tax-GST/HST (100%) - GST expense is 100% deductible according to CRA rules
Tourism Levy: Travel-Taxes (100%) - Tourism Levy is a tax expense related to travel, which is 100% deductible according to CRA rules
Restaurant Room Charge: Travel-Meals (50%) - Restaurant Room Charge implies a meal expense, which is 50% deductible according to CRA rules (ITA Section 67.1)
Restaurant Room Charge: Travel-Meals (50%) - Restaurant Room Charge implies a meal expense, which is 50% deductible according to CRA rules (ITA Section 67.1)
Room Charge: Travel-Lodging (100%) - Room Charge is a lodging expense, which is 100% deductible according to CRA rules
Marketing Fee: Uncategorized-Review-Required (0%) - Marketing Fee is ambiguous and may be personal or business-related, requiring manual review ⭐
Gst 767657513: Tax-GST/HST (100%) - GST expense is 100% deductible according to CRA rules
Tourism Levy: Travel-Taxes (100%) - Tourism Levy is a tax expense related to travel, which is 100% deductible according to CRA rules
```

---

## Agent Performance Details

### Check Agent Execution
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq '.agent_details.agent_results'
```

**Result:**
```json
[
  {
    "agent_name": "DataExtractionAgent",
    "success": true,
    "confidence_score": 1.0,
    "processing_time": 11.40,
    "error_message": null
  },
  {
    "agent_name": "CRArulesAgent",
    "success": true,
    "confidence_score": 0.7,
    "processing_time": 3.34,
    "error_message": null
  }
]
```

- ✅ **DataExtractionAgent**: 100% confidence (Gemini extraction successful)
- ✅ **CRArulesAgent**: 70% confidence (TogetherAI + RAG categorization)
- **Overall Confidence**: 85%

---

## Analysis

### ✅ Agents System Advantages

1. **More Conservative for CRA Compliance**
   - Flags ambiguous items (Marketing Fee) for manual review
   - Better audit protection
   - Reduces risk of claiming personal expenses

2. **Contextual Reasoning with Citations**
   - References ITA Section 67.1 for meals (50% rule)
   - Provides reasoning for each categorization
   - Defensible in audit scenarios

3. **RAG Integration**
   - Queries CRA tax law documents for context
   - Can incorporate latest tax regulations
   - More intelligent than static keyword matching

### ⚡ Baseline System Advantages

1. **Faster Processing**
   - ~5-10 seconds vs ~15 seconds
   - Better for high-volume batch processing

2. **Deterministic & Transparent**
   - Same input always produces same output
   - Clear rule names show exact matching logic
   - Easier to debug and validate

3. **Simpler Architecture**
   - No LLM API calls for categorization
   - Lower operational costs
   - No rate limiting concerns

---

## Recommendation Matrix

| Scenario | Recommended Approach | Reason |
|----------|---------------------|---------|
| High-value expenses (>$1000) | **Agents** | Conservative categorization, audit protection |
| Complex/ambiguous receipts | **Agents** | Better at identifying items needing review |
| Batch processing (100+ receipts) | **Baseline** | Faster, more cost-effective |
| Simple receipts (office supplies, gas) | **Baseline** | Deterministic, transparent rules |
| Tax audit preparation | **Agents** | Citations and reasoning documentation |
| Development/testing | **Baseline** | Consistent results, easier debugging |

---

## Conclusion

Both systems **work correctly** but serve different purposes:

- **Baseline** is optimized for speed, transparency, and deterministic results
- **Agents** is optimized for accuracy, compliance, and intelligent review flagging

The **$10.50 difference** is **intentional conservative categorization** by the agents system, making it more suitable for CRA compliance scenarios where avoiding questionable deductions is preferred.

### Test Status: ✅ PASSED

Both endpoints are functioning as designed. The agents system successfully:
- ✅ Integrates with RAG database for CRA tax law context
- ✅ Provides more conservative categorization than baseline
- ✅ Flags ambiguous items for manual review
- ✅ Includes ITA section citations in reasoning
- ✅ Achieves 85% confidence with proper agent orchestration

---

## Bug Fixed During Testing

**Issue**: CRArulesAgent was timing out at 2 seconds default
**Fix**: Updated `src/quickexpense/core/dependencies.py` to use 30-second timeout:

```python
def get_multi_agent_orchestrator(settings: Settings) -> AgentOrchestrator:
    # Use longer timeouts for complex processing
    data_extraction_agent = DataExtractionAgent(settings=settings, timeout_seconds=30.0)
    cra_rules_agent = CRArulesAgent(settings=settings, timeout_seconds=30.0)
    return AgentOrchestrator(...)
```

**Additional Fix**: Added type conversion for `tax_amount` and `tip_amount` in `CRArulesAgent._add_tax_and_tip_items()` to handle string/float mismatches.
