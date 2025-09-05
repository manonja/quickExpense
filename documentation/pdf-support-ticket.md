# PDF Receipt Support Enhancement

**Ticket ID**: PRE-105
**Priority**: Medium
**Type**: Feature Enhancement
**Estimated Effort**: 2-3 days

## Problem Statement

Current receipt processing endpoint (`/api/v1/receipts/extract`) only accepts image formats (JPEG, PNG, GIF, BMP, WEBP). Many users have receipts in PDF format that need to be processed.

## Current Limitation

- Gemini API expects image input
- Base64 encoded PDFs are rejected as invalid images
- Users must manually convert PDFs to images before uploading

## Proposed Solution

Add automatic PDF-to-image conversion in the receipt processing pipeline.

## Implementation Details

### 1. Add PDF Processing Dependencies
```toml
# pyproject.toml
dependencies = [
    # ... existing deps
    "pdf2image>=1.16.0",  # PDF to image conversion
    "pypdf>=3.17.0",      # PDF validation
]
```

### 2. Update Receipt Extraction Request
```python
# models/receipt.py
class ReceiptExtractionRequest(BaseModel):
    file_base64: str = Field(..., description="Base64 encoded file data (image or PDF)")
    file_type: str | None = Field(None, description="File type: 'pdf' or 'image'")
    category: str
    additional_context: str | None = None
```

### 3. Add PDF Converter Service
```python
# services/pdf_converter.py
from pdf2image import convert_from_bytes
from io import BytesIO
import base64

class PDFConverterService:
    async def convert_pdf_to_image(self, pdf_base64: str, page: int = 0) -> str:
        """Convert PDF page to image base64."""
        pdf_bytes = base64.b64decode(pdf_base64)
        images = convert_from_bytes(pdf_bytes, dpi=300, first_page=page+1, last_page=page+1)

        if not images:
            raise ValueError("Failed to convert PDF")

        # Convert PIL image to base64
        buffer = BytesIO()
        images[0].save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
```

### 4. Update Gemini Service
```python
# services/gemini.py
async def extract_receipt_data(
    self,
    file_base64: str,
    file_type: str | None = None,
    additional_context: str | None = None,
) -> ExtractedReceipt:
    # Auto-detect PDF if not specified
    if file_type == "pdf" or self._is_pdf(file_base64):
        pdf_converter = PDFConverterService()
        image_base64 = await pdf_converter.convert_pdf_to_image(file_base64)
    else:
        image_base64 = file_base64

    # Continue with existing image processing...
```

## Acceptance Criteria

1. ✅ Endpoint accepts PDF files encoded as base64
2. ✅ PDFs are automatically converted to images for processing
3. ✅ Multi-page PDFs process first page only (or configurable)
4. ✅ Error handling for corrupted PDFs
5. ✅ Performance: PDF conversion < 2 seconds for typical receipts
6. ✅ Updated API documentation
7. ✅ Unit tests for PDF conversion
8. ✅ Integration tests with sample PDFs

## Testing Plan

1. Test with various PDF formats (single/multi-page, scanned, text-based)
2. Test error cases (corrupted PDF, password-protected)
3. Performance testing with large PDFs
4. Test file type auto-detection

## API Usage Example

```bash
# Convert PDF to base64
base64 -i receipt.pdf > receipt_pdf.b64

# Send to API (auto-detects PDF)
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d "{
    \"file_base64\": \"$(cat receipt_pdf.b64)\",
    \"category\": \"Travel\"
  }"

# Or explicitly specify file type
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d "{
    \"file_base64\": \"$(cat receipt_pdf.b64)\",
    \"file_type\": \"pdf\",
    \"category\": \"Travel\"
  }"
```

## Dependencies

- pdf2image: Requires system package `poppler-utils`
- Installation:
  - macOS: `brew install poppler`
  - Ubuntu: `apt-get install poppler-utils`
  - Windows: Download from https://blog.alivate.com.au/poppler-windows/

## Future Enhancements

1. Support for multi-page receipt processing
2. OCR enhancement for low-quality scans
3. Support for other document formats (DOCX, email attachments)
