# Testing Agents API with RAG

This document shows how to test the multi-agent system with RAG (Retrieval Augmented Generation) for CRA tax law compliance.

## Quick Test

```bash
# Test with a single receipt
uv run python scripts/test_agents_with_real_receipts.py \
  /Users/manonjacquin/Documents/receipts/marriot.pdf \
  "Hotel accommodation for business conference"
```

## What Gets Tested

1. **RAG Database**: Initialized with CRA tax law documents
2. **DataExtractionAgent**: Uses Gemini to extract receipt data (images/PDFs)
3. **CRArulesAgent**: Applies Canadian tax rules using RAG context + TogetherAI LLM

## Example Output

```
✅ RAG database initialized

📄 Receipt: marriot.pdf
📝 Context: Hotel accommodation for business conference
📊 Size: 83.8 KB

🤖 Processing with agents + RAG...

======================================================================
RESULTS
======================================================================
Success: True
Overall Confidence: 85.00%
Processing Time: 16.19s
Consensus: simple_average

🤖 AGENTS
✅ DataExtractionAgent: 100.00% (11.40s)
✅ CRArulesAgent: 70.00% (4.80s)

📋 EXPENSE
Vendor: Courtyard by Marriott
Date: 2025-04-24
Total: $535.46

🇨🇦 CRA ANALYSIS
Category: Travel-Lodging
Deductibility: 100%

📝 LINE ITEMS (11)
1. Restaurant Room Charge: $40.70 → Travel-Meals (50%)
2. Room Charge: $175.00 → Travel-Lodging (100%)
3. Marketing Fee: $5.25 → Uncategorized-Review-Required (0%)
4. GST: $9.01 → Tax-GST/HST (100%)
5. Tourism Levy: $7.21 → Travel-Taxes (100%)
```

## CRA Rules Applied

The system correctly applied these CRA rules:

- **Meals & Entertainment**: 50% deductible (ITA Section 67.1)
- **Lodging**: 100% deductible
- **GST/HST**: 100% deductible (Input Tax Credit)
- **Tourism Levy**: 100% deductible (travel tax)
- **Marketing Fee**: Flagged for manual review (unclear business purpose)

## RAG Context

The CRArulesAgent queries the RAG database with:
- Line item descriptions
- Vendor name for context
- Expense category hints

RAG results are injected into the LLM prompt with:
- Citation IDs (e.g., "T4002-####")
- Source URLs
- Relevant CRA document excerpts

## Available Test Receipts

In `/Users/manonjacquin/Documents/receipts`:
- `Harrods.jpg` - Department store shopping
- `marriot.pdf` - Hotel invoice with detailed line items
- `marriot.png` - Hotel invoice (image format)
- `IMG_7597.HEIC` - iPhone HEIC photo
- `IMG_7598.HEIC` - iPhone HEIC photo
- `15-Sep-2025.jpeg` - Date-labeled receipt

## Testing Individual Components

### 1. Test RAG Helper Only

```bash
uv run python scripts/test_rag_helper.py
```

This tests the RAG context retrieval without full agent orchestration.

### 2. Test via API Endpoint

```bash
# Start server
uv run fastapi dev src/quickexpense/main.py

# Test with curl
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@/Users/manonjacquin/Documents/receipts/marriot.pdf" \
  -F "additional_context=Hotel for business conference"
```

### 3. Test via Web UI

```bash
# Start server
uv run fastapi dev src/quickexpense/main.py

# Open browser
open http://localhost:8000

# Toggle "Use Agent Processing"
# Upload receipt
# Review agent breakdown in results
```

## Troubleshooting

### Gemini API Errors

If you see `500 Internal error encountered`, try:
1. Check GEMINI_API_KEY in `.env`
2. Try a different receipt (Gemini sometimes has issues with specific images)
3. Use PDF format instead of images

### Agent Timeout

If agents timeout (< 85% confidence), increase timeout:

```python
data_extraction_agent = DataExtractionAgent(settings=settings, timeout_seconds=30.0)
cra_rules_agent = CRArulesAgent(settings=settings, timeout_seconds=30.0)
```

### RAG Not Finding Documents

If you see "No specific CRA documents found":
- This is expected for certain expense types
- The agent falls back to general CRA tax knowledge
- Still produces valid categorizations

## Architecture

```
Receipt → DataExtractionAgent (Gemini) → Receipt JSON
                                             ↓
                                    CRArulesAgent (RAG + TogetherAI)
                                             ↓
                                    Categorized Line Items
                                    with CRA compliance
```

## Next Steps

1. Add more CRA documents to RAG database
2. Test with more receipt types (fuel, office supplies, professional services)
3. Validate against real CRA guidelines
4. Add confidence score thresholds for auto-processing
