# QuickExpense API Quick Reference

## Server

```bash
# Start development server with auto-reload
uv run fastapi dev src/quickexpense/main.py

# Access at: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## Receipt Processing Endpoints

### 1. Baseline Processing (Gemini + Business Rules)

**Endpoint**: `POST /api/web/upload-receipt`

**Use when**: Fast processing, simple receipts, deterministic results needed

```bash
curl -X POST http://localhost:8000/api/web/upload-receipt \
  -F "file=@/path/to/receipt.pdf" \
  -F "additional_context=Business lunch with client" \
  -F "dry_run=true"
```

**Parameters**:
- `file`: Receipt file (JPEG, PNG, PDF, HEIC)
- `additional_context`: Business context (optional)
- `dry_run`: Preview without creating QB expense (true/false)

**Response highlights**:
```json
{
  "receipt_info": { "vendor_name": "...", "total_amount": 100.00 },
  "business_rules": {
    "applied_rules": [
      {
        "description": "Item",
        "category": "Travel-Meals",
        "deductible_percentage": 50,
        "rule_applied": "room_service_meals"
      }
    ]
  },
  "tax_deductibility": {
    "deductible_amount": "50.00",
    "deductibility_rate": "50.0"
  }
}
```

### 2. Multi-Agent Processing (AI + RAG)

**Endpoint**: `POST /api/web/upload-receipt-agents`

**Use when**: Complex receipts, CRA compliance critical, ambiguity detection needed

```bash
curl -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@/path/to/receipt.pdf" \
  -F "additional_context=Hotel for business conference" \
  -F "dry_run=true"
```

**Parameters**: Same as baseline

**Response highlights**:
```json
{
  "agent_details": {
    "overall_confidence": 0.85,
    "agent_results": [
      {
        "agent_name": "DataExtractionAgent",
        "success": true,
        "confidence_score": 1.0
      },
      {
        "agent_name": "CRArulesAgent",
        "success": true,
        "confidence_score": 0.7
      }
    ],
    "full_agent_data": {
      "line_items": [
        {
          "original_description": "Marketing Fee",
          "category": "Uncategorized-Review-Required",
          "deductibility_percent": 0,
          "reasoning": "Ambiguous and may be personal...",
          "citations": []
        }
      ],
      "total_deductible": 453.70
    }
  }
}
```

---

## Useful Query Examples

### Get Summary Comparison

**Baseline**:
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt \
  -F "file=@receipt.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq '{
      method: "baseline",
      total: .receipt_info.total_amount,
      deductible: .tax_deductibility.deductible_amount,
      rate: .tax_deductibility.deductibility_rate,
      categories: [.business_rules.applied_rules[].category] | unique
    }'
```

**Agents**:
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@receipt.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq '{
      method: "agents",
      total: (.receipt_info.total_amount | tonumber),
      deductible: .agent_details.full_agent_data.total_deductible,
      rate: (.agent_details.full_agent_data.deductibility_rate | tonumber),
      categories: [.agent_details.full_agent_data.line_items[].category] | unique,
      confidence: .agent_details.overall_confidence
    }'
```

### View Line Items with Reasoning

**Baseline**:
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt \
  -F "file=@receipt.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq -r '.business_rules.applied_rules[] |
      "\(.description): \(.category) (\(.deductible_percentage)%) - \(.rule_name)"'
```

**Agents**:
```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@receipt.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq -r '.agent_details.full_agent_data.line_items[] |
      "\(.original_description): \(.category) (\(.deductibility_percent)%) - \(.reasoning)"'
```

### Check Agent Performance

```bash
curl -s -X POST http://localhost:8000/api/web/upload-receipt-agents \
  -F "file=@receipt.pdf" \
  -F "additional_context=Hotel" \
  -F "dry_run=true" \
  | jq '{
      agents: .agent_details.agent_results,
      confidence: .agent_details.overall_confidence,
      flags: .agent_details.flags_for_review
    }'
```

---

## API v1 Endpoints (Direct)

### Process with Multi-Agent System

```bash
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@receipt.pdf" \
  -F "additional_context=Business expense"
```

**Returns**: JSON with consensus results, agent breakdown, CRA categorization

### Extract Receipt Data Only (Gemini)

```bash
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "<base64_encoded_file>",
    "category": "Travel",
    "additional_context": "Hotel stay"
  }'
```

### Create Expense Directly (No AI)

```bash
curl -X POST http://localhost:8000/api/v1/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Office Depot",
    "amount": 45.99,
    "date": "2024-01-15",
    "currency": "CAD",
    "category": "Office Supplies"
  }'
```

---

## Authentication Endpoints

### Check QuickBooks Status

```bash
curl http://localhost:8000/api/web/auth-status
```

### Get OAuth URL

```bash
curl http://localhost:8000/api/web/auth-url
```

---

## Test Files Location

Your test receipts are in:
```
/Users/manonjacquin/Documents/receipts/
├── Harrods.jpg          # Department store
├── marriot.pdf          # Hotel invoice (best for testing)
├── marriot.png          # Hotel invoice (image)
├── IMG_7597.HEIC        # iPhone HEIC photo
├── IMG_7598.HEIC        # iPhone HEIC photo
└── 15-Sep-2025.jpeg     # Date-labeled receipt
```

---

## Tips

1. **Use dry_run=true** for testing without creating QuickBooks expenses
2. **Pipe to jq** for readable JSON: `... | jq '.'`
3. **Save responses** for comparison: `... > baseline_result.json`
4. **Check server logs** if issues occur: FastAPI dev mode shows detailed logs
5. **Use -s flag** with curl to hide progress bars: `curl -s ...`

---

## Common Issues

### Agent Timeout
**Symptom**: `"error_message": "Agent CRArulesAgent timed out after 2.0s"`

**Fix**: Already fixed in `dependencies.py` (30s timeout), restart server if needed

### Gemini API Error
**Symptom**: `500 Internal error encountered`

**Solution**:
- Check GEMINI_API_KEY in `.env`
- Try different receipt file
- Use PDF format instead of images

### No Line Items Returned
**Check**:
```bash
curl -s ... | jq '.agent_details.full_agent_data.line_items | length'
```

If 0, check agent_results for errors.

---

## See Also

- [AGENTS_VS_BASELINE_TEST_RESULTS.md](AGENTS_VS_BASELINE_TEST_RESULTS.md) - Detailed comparison
- [TEST_AGENTS_RAG.md](TEST_AGENTS_RAG.md) - Testing guide
- API Docs: http://localhost:8000/docs (when server running)
