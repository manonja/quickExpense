# PRE-108: Universal File Processing Infrastructure

**Type:** Story
**Priority:** High
**Effort:** 4 Story Points
**Sprint:** Foundation Layer

## User Story
**As a** small business owner
**I want** to upload receipts in any common format (PDF, JPEG, PNG, etc.)
**So that** I don't need to manually convert files before processing expenses

## Business Value
- **Problem:** Current system only accepts image formats, forcing users to convert PDF receipts manually
- **Impact:** Poor user experience, workflow friction, potential user abandonment
- **Solution:** Universal file processor that handles all common receipt formats transparently

## Description
Create a universal file processing infrastructure that automatically detects file types and converts them to the appropriate format for AI processing. The system should handle PDFs, images, and future formats while providing consistent processing capabilities and error handling.

## Acceptance Criteria

### AC1: Universal File Type Detection
- [ ] System auto-detects file type from base64 content (magic number detection)
- [ ] Supports explicit file type specification via API parameter
- [ ] Handles corrupted or invalid files gracefully with clear error messages
- [ ] Validates file size limits (max 10MB per file)
- [ ] Logs file processing metrics for monitoring
- [ ] Supports file type override for edge cases

### AC2: PDF Processing Capabilities
- [ ] PDF-to-image conversion using pdf2image library
- [ ] Configurable DPI settings (default 300 DPI for receipt quality)
- [ ] Multi-page PDF support (processes first page by default)
- [ ] Handles password-protected PDFs with appropriate error messages
- [ ] Supports page selection for multi-page documents
- [ ] Converts to PNG format for consistent AI processing

### AC3: Image Processing Capabilities
- [ ] Supports all major image formats (JPEG, PNG, GIF, BMP, WEBP)
- [ ] Image optimization for AI processing (resize if too large)
- [ ] Maintains aspect ratio during resizing
- [ ] Handles corrupted image files gracefully
- [ ] Preserves image quality for text extraction
- [ ] Converts all formats to consistent internal format

### AC4: Processing Pipeline Architecture
- [ ] Modular processor design allowing easy addition of new formats
- [ ] Async processing for better performance
- [ ] Caching of converted files to avoid reprocessing
- [ ] Processing time optimization (<2 seconds for typical files)
- [ ] Memory efficient processing for large files
- [ ] Cleanup of temporary files after processing

### AC5: Error Handling and Logging
- [ ] Comprehensive error handling for all file processing failures
- [ ] Clear error messages for unsupported formats
- [ ] Detailed logging of processing steps for debugging
- [ ] Performance metrics collection (processing time, file sizes)
- [ ] Rate limiting protection against abuse
- [ ] Graceful degradation when external dependencies fail

## Technical Implementation

### Files to Create
- `src/quickexpense/services/file_processor.py` - Universal file processor
- `src/quickexpense/services/pdf_converter.py` - PDF-specific processing
- `src/quickexpense/services/image_processor.py` - Image-specific processing
- `src/quickexpense/models/file_processing.py` - File processing models
- `tests/services/test_file_processor.py` - Comprehensive tests

### Dependencies to Add
```toml
# pyproject.toml additions
dependencies = [
    # ... existing deps
    "pdf2image>=1.16.0",  # PDF to image conversion
    "pypdf>=3.17.0",      # PDF validation and metadata
    "pillow>=10.0.0",     # Enhanced image processing
    "python-magic>=0.4.27",  # File type detection
]
```

### Core Architecture
```python
class UniversalFileProcessor:
    """Universal file processor handling all receipt formats."""

    def __init__(self):
        self.pdf_converter = PDFConverter()
        self.image_processor = ImageProcessor()
        self.cache = ProcessingCache()

    async def process_file(
        self,
        file_base64: str,
        file_type: str | None = None,
        processing_options: ProcessingOptions | None = None
    ) -> ProcessedFile:
        """Process any file type and return standardized result."""

        # 1. Detect file type
        detected_type = self._detect_file_type(file_base64, file_type)

        # 2. Check cache
        cache_key = self._generate_cache_key(file_base64, processing_options)
        if cached := await self.cache.get(cache_key):
            return cached

        # 3. Route to appropriate processor
        if detected_type == "pdf":
            result = await self.pdf_converter.convert_to_image(file_base64, processing_options)
        elif detected_type in SUPPORTED_IMAGE_FORMATS:
            result = await self.image_processor.process_image(file_base64, processing_options)
        else:
            raise UnsupportedFileTypeError(f"Unsupported file type: {detected_type}")

        # 4. Cache result
        await self.cache.set(cache_key, result)

        return result

class PDFConverter:
    """Specialized PDF processing."""

    async def convert_to_image(
        self,
        pdf_base64: str,
        options: ProcessingOptions | None = None
    ) -> ProcessedFile:
        """Convert PDF to image for AI processing."""

        try:
            pdf_bytes = base64.b64decode(pdf_base64)

            # Validate PDF
            self._validate_pdf(pdf_bytes)

            # Convert with configurable options
            dpi = options.dpi if options else 300
            page = options.page if options else 0

            images = convert_from_bytes(
                pdf_bytes,
                dpi=dpi,
                first_page=page + 1,
                last_page=page + 1,
                fmt='PNG'
            )

            if not images:
                raise PDFProcessingError("Failed to convert PDF to image")

            # Convert to base64
            buffer = BytesIO()
            images[0].save(buffer, format="PNG", optimize=True)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()

            return ProcessedFile(
                content_base64=image_base64,
                original_type="pdf",
                processed_type="png",
                processing_time=time.time() - start_time,
                metadata={"dpi": dpi, "page": page}
            )

        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise PDFProcessingError(f"PDF processing failed: {e}") from e
```

### Models
```python
class ProcessingOptions(BaseModel):
    """Options for file processing."""
    dpi: int = Field(default=300, ge=150, le=600)
    page: int = Field(default=0, ge=0)
    max_width: int = Field(default=2048, ge=512)
    max_height: int = Field(default=2048, ge=512)
    quality: int = Field(default=95, ge=70, le=100)

class ProcessedFile(BaseModel):
    """Result of file processing."""
    content_base64: str
    original_type: str
    processed_type: str
    processing_time: float
    file_size: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    cache_key: str | None = None
```

## Testing Requirements

### Unit Tests
- [ ] File type detection tests with various formats
- [ ] PDF conversion tests with different page counts
- [ ] Image processing tests with different formats
- [ ] Error handling tests for corrupted files
- [ ] Cache functionality tests
- [ ] Performance tests for large files

### Integration Tests
- [ ] End-to-end processing with real receipt files
- [ ] Marriott PDF processing test
- [ ] Mixed format processing tests
- [ ] Concurrent processing tests
- [ ] Memory usage tests with large files
- [ ] External dependency failure tests

### Test Data
```python
# Test file examples
TEST_FILES = {
    "marriott_hotel_bill.pdf": "Base64 encoded Marriott PDF",
    "office_receipt.jpg": "Base64 encoded image receipt",
    "corrupted_file.pdf": "Intentionally corrupted PDF for error testing",
    "multi_page_invoice.pdf": "Multi-page PDF for page selection testing",
    "large_receipt.png": "Large image for resizing tests"
}
```

## Dependencies
- System dependencies: `poppler-utils` for PDF processing
- None from other tickets (foundational infrastructure)

## Definition of Done
- [ ] All acceptance criteria met and verified
- [ ] Processes PDF and image files reliably
- [ ] Error handling covers all failure scenarios
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate real-world file processing
- [ ] Performance requirements met (<2s processing time)
- [ ] Memory usage optimized for large files
- [ ] Code review completed and approved
- [ ] Documentation includes setup instructions and API guide

## Validation Scenarios

### Scenario 1: Marriott PDF Processing
**Given** a PDF Marriott hotel bill
**When** uploaded through the file processor
**Then** PDF is converted to high-quality PNG image ready for AI extraction

### Scenario 2: Mixed Format Batch
**Given** multiple receipts in different formats (PDF, JPEG, PNG)
**When** processed through the universal processor
**Then** all files are converted to consistent format for downstream processing

### Scenario 3: Large File Handling
**Given** a large PDF file (5MB+)
**When** processed through the system
**Then** file is processed efficiently without memory issues

### Scenario 4: Corrupted File Handling
**Given** a corrupted or invalid file
**When** uploaded to the processor
**Then** system returns clear error message without crashing

### Scenario 5: Multi-page PDF Selection
**Given** a multi-page PDF with receipt on page 2
**When** processed with page selection option
**Then** correct page is extracted and converted

## Risk Mitigation
- **External Dependencies:** Graceful handling of poppler-utils availability
- **Memory Usage:** Streaming processing for large files, proper cleanup
- **Security:** File type validation, size limits, malware protection considerations
- **Performance:** Caching, async processing, optimization for common file sizes

## Success Metrics
- Processes 99%+ of valid receipt files successfully
- Processing time <2 seconds for typical files (under 2MB)
- Memory usage remains stable under load
- Zero security vulnerabilities in file processing
- Support covers 95%+ of user's receipt formats
