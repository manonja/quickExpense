# PRE-108: Universal File Processing Infrastructure

## Overview

This document describes the implementation of the universal file processing infrastructure for QuickExpense, which enables support for various receipt formats including PDFs and all common image formats.

## Architecture

### Core Components

1. **FileProcessorService** (`src/quickexpense/services/file_processor.py`)
   - Auto-detection of file types using magic bytes
   - Validation of file content and size
   - Orchestration of format conversions
   - Error handling for corrupted files

2. **PDFConverterService** (`src/quickexpense/services/pdf_converter.py`)
   - PDF to image conversion using pdf2image
   - High-quality rendering at 300 DPI
   - Multi-page PDF support
   - Metadata extraction from PDFs

3. **FileType Enum** 
   - Comprehensive type system for supported formats
   - Helper methods for type checking
   - MIME type and extension mappings

## Supported Formats

### Image Formats
- JPEG/JPG
- PNG
- GIF
- BMP
- WebP

### Document Formats
- PDF (converted to PNG for AI processing)

## Usage Examples

### CLI Usage
```bash
# Process an image receipt
quickexpense upload receipt.jpg

# Process a PDF receipt
quickexpense upload invoice.pdf
```

### API Usage
```python
# Extract from PDF
curl -X POST http://localhost:8000/api/v1/receipts/extract \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "<base64_pdf_content>",
    "category": "Travel"
  }'
```

### Direct Service Usage
```python
from quickexpense.services.file_processor import FileProcessorService

service = FileProcessorService()

# Process any file type
processed = await service.process_file(file_base64)
print(f"Original type: {processed.original_file_type}")
print(f"Processed type: {processed.file_type}")

if processed.original_file_type.is_pdf:
    print(f"PDF pages: {processed.processing_metadata['pdf_pages']}")
```

## Implementation Details

### File Type Detection

Files are detected using magic bytes (file signatures):
```python
MAGIC_BYTES = {
    b"\xFF\xD8\xFF": FileType.JPEG,
    b"\x89PNG\r\n\x1a\n": FileType.PNG,
    b"%PDF": FileType.PDF,
    # ... more signatures
}
```

### PDF Conversion Process

1. Validate PDF integrity using pypdf
2. Convert PDF to high-resolution PNG (300 DPI)
3. Resize if needed while maintaining aspect ratio
4. Return base64 encoded PNG for AI processing

### Error Handling

The system handles various error scenarios:
- `UnsupportedFileTypeError`: Unknown or unsupported format
- `CorruptedFileError`: Invalid or corrupted file content
- `FileProcessingError`: General processing failures

### Performance Considerations

- PDF conversion is CPU-intensive; consider caching for repeated processing
- Large PDFs are handled page-by-page to avoid memory issues
- Image resizing maintains quality while reducing processing time

## Testing

### Unit Tests
```bash
# Run file processor tests
uv run pytest tests/unit/test_file_processor.py -v
```

### Integration Testing
```bash
# Test PDF conversion manually
uv run python scripts/test_pdf_conversion.py sample.pdf
```

### Test Coverage
- File type detection for all supported formats
- PDF to image conversion
- Error handling for corrupted files
- Size validation
- Base64 encoding/decoding

## System Requirements

### PDF Support
PDF processing requires system libraries:

**macOS:**
```bash
brew install poppler
```

**Ubuntu/Debian:**
```bash
sudo apt-get install poppler-utils
```

**Windows:**
- Download poppler binaries from: https://github.com/oschwartz10612/poppler-windows/releases
- Add to PATH

## Future Enhancements

1. **Additional Formats**
   - TIFF support for scanned documents
   - HEIC/HEIF for modern iOS photos
   - Multi-page TIFF support

2. **Processing Optimizations**
   - Parallel page processing for multi-page PDFs
   - Caching layer for repeated conversions
   - Progressive loading for large files

3. **Advanced Features**
   - OCR enhancement for low-quality scans
   - Image quality assessment
   - Automatic rotation detection
   - Receipt edge detection and cropping

## Integration Points

The file processor integrates seamlessly with:
- **Gemini AI Service**: Processes converted images for data extraction
- **CLI**: Validates and processes uploaded files
- **API**: Handles base64 encoded files in requests
- **Multi-category Models**: Supports complex receipt processing

## Error Messages

Common error messages users might encounter:
- "Unsupported file format" - File type not recognized
- "File too large" - File exceeds 50MB limit
- "Invalid or corrupted PDF" - PDF cannot be read
- "PDF support not installed" - Missing system dependencies

## Monitoring

Key metrics to monitor:
- File type distribution
- Conversion success rates
- Processing times by format
- Error rates by type
- Memory usage during PDF conversion