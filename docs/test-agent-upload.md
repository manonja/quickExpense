# Testing Multi-Agent Receipt Processing with File Upload

This guide shows how to test the multi-agent receipt processing system using direct file uploads.

## Prerequisites

1. Start the FastAPI server:
```bash
cd /Users/manonjacquin/Documents_local/POCs/quickExpense
uv run fastapi dev src/quickexpense/main.py
```

## Testing with curl

### Basic Usage
```bash
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@/Users/manonjacquin/Documents/receipts/IMG_7597.HEIC" \
  -F "additional_context=Business expense receipt"
```

### Pretty-print JSON output
```bash
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@/Users/manonjacquin/Documents/receipts/IMG_7597.HEIC" \
  -F "additional_context=Business expense receipt" \
  | python -m json.tool
```

### Save output to file
```bash
curl -X POST http://localhost:8000/api/v1/receipts/process-file \
  -F "receipt=@/Users/manonjacquin/Documents/receipts/IMG_7597.HEIC" \
  -F "additional_context=Business expense receipt" \
  -o agent_result.json
```

## Testing with httpie (if installed)

```bash
# Install httpie if needed
pip install httpie

# Upload and process receipt
http --form POST localhost:8000/api/v1/receipts/process-file \
  receipt@/Users/manonjacquin/Documents/receipts/IMG_7597.HEIC \
  additional_context="Business expense receipt"
```

## What You'll See

### In the Server Terminal:
- Receipt file upload details (filename, size, format)
- Agent initialization messages
- Processing steps for each agent:
  - DataExtractionAgent using Gemini
  - CRArulesAgent applying tax rules
  - TaxCalculatorAgent validating calculations
- Consensus building between agents
- Final result compilation

### In the Response:
```json
{
  "success": true,
  "overall_confidence": 0.92,
  "vendor_name": "Restaurant Name",
  "transaction_date": "2024-01-15",
  "total_amount": 45.20,
  "subtotal": 40.00,
  "tax_amount": 5.20,
  "category": "Meals & Entertainment",
  "deductibility_percentage": 50,
  "qb_account": "Travel - Meals & Entertainment",
  "ita_section": "Section 67.1",
  "audit_risk": "low",
  "calculated_gst_hst": 5.20,
  "deductible_amount": 22.60,
  "tax_validation_result": "valid",
  "processing_time": 12.34,
  "consensus_method": "unanimous",
  "flags_for_review": [],
  "agent_results": [
    {
      "agent_name": "DataExtractionAgent",
      "success": true,
      "confidence_score": 0.95,
      "processing_time": 3.2,
      "error_message": null
    },
    ...
  ]
}
```

## Monitoring Logs

### View real-time processing logs
```bash
# In another terminal
tail -f data/logs/quickexpense_*.log
```

### Enable debug logging for more details
```bash
# Before starting the server
export LOG_LEVEL=DEBUG
uv run fastapi dev src/quickexpense/main.py
```

## Supported File Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- PDF (.pdf)
- HEIC/HEIF (.heic, .heif) - iPhone photos
- GIF (.gif)
- BMP (.bmp)
- WebP (.webp)

## Common Issues

### Server not running
```
Error: Could not connect to server
Solution: Make sure server is running with: uv run fastapi dev src/quickexpense/main.py
```

### File too large
```
Error: File too large (15.2MB). Maximum size: 10MB
Solution: Reduce file size or use a smaller image
```

### Unsupported format
```
Error: Unsupported file format '.docx'. Supported: .jpg, .jpeg, .png, .pdf, .heic, .heif, .gif, .bmp, .webp
Solution: Convert to a supported format
```
