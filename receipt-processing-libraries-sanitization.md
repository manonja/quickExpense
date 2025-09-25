# Receipt Processing Libraries and Sanitization Details

## Libraries Used for Receipt Processing

### 1. **Pillow (PIL)**
- **Package**: `pillow>=10.0.0`
- **Purpose**: Image manipulation and format conversion
- **Usage**:
  - Opening and validating image files
  - Resizing images that exceed maximum dimensions (2048x2048)
  - Converting between image formats
  - Image thumbnail generation with LANCZOS resampling

### 2. **PyMuPDF (fitz)**
- **Package**: `pymupdf>=1.23.0`
- **Purpose**: PDF processing and conversion
- **Usage**:
  - Opening and validating PDF files
  - Converting PDF pages to PNG images at 300 DPI
  - Extracting PDF metadata (page count, dimensions, encryption status)
  - Multi-page PDF handling

### 3. **Google Generative AI (Gemini)**
- **Package**: `google-generativeai>=0.8.0`
- **Purpose**: AI-powered OCR and data extraction
- **Model**: `gemini-2.0-flash-exp` (configurable)
- **Usage**:
  - Receipt text extraction from images
  - Structured data parsing with JSON schema
  - Multi-language support
  - Confidence scoring

### 4. **Python Standard Library**
- **base64**: Encoding/decoding file content for API transmission
- **io.BytesIO**: In-memory file operations
- **json**: Parsing Gemini API responses

## File Type Support and Processing

### Supported Image Formats
- **JPEG/JPG**: Magic bytes `\xff\xd8\xff`
- **PNG**: Magic bytes `\x89PNG\r\n\x1a\n`
- **GIF**: Magic bytes `GIF87a` or `GIF89a`
- **BMP**: Magic bytes `BM`
- **WebP**: Magic bytes `RIFF` + `WEBP` check
- **PDF**: Magic bytes `%PDF`

**Note**: HEIC format is NOT directly supported. HEIC files would need external conversion before processing.

## Sanitization Steps by File Type

### 1. **Initial File Validation** (All Types)
```python
# File size validation
MIN_FILE_SIZE = 100 bytes        # Too small to be valid receipt
MAX_FILE_SIZE = 50 MB            # Maximum allowed size

# Magic byte verification
- Reads file header to detect actual file type
- Compares detected type with declared type
- Rejects mismatched file types
```

### 2. **Base64 Encoding/Decoding**
- All files are converted to base64 for safe transmission
- Validation occurs during decoding to catch corrupted data
- Failed decoding raises `CorruptedFileError`

### 3. **Image Files (JPEG, PNG, GIF, BMP, WebP)**

#### Sanitization Steps:
1. **Format Validation**: Magic bytes verification
2. **Size Validation**: 100 bytes < file < 50MB
3. **PIL Image Validation**:
   ```python
   image = Image.open(BytesIO(image_data))  # Validates image structure
   ```
4. **Dimension Constraints**:
   ```python
   MAX_IMAGE_SIZE = (2048, 2048)
   image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
   ```
5. **Memory Safety**: Images processed in memory using BytesIO

#### No Additional Sanitization:
- No EXIF stripping
- No metadata removal
- No re-encoding (unless resizing)
- Original image data preserved

### 4. **PDF Files**

#### Sanitization Steps:
1. **Format Validation**: Magic bytes `%PDF` verification
2. **Size Validation**: Same as images
3. **PyMuPDF Validation**:
   ```python
   doc = fitz.open(stream=pdf_bytes, filetype="pdf")
   # Validates PDF structure
   # Checks page count > 0
   # Verifies first page accessibility
   ```
4. **Conversion to PNG**:
   - Renders at 300 DPI for quality
   - Converts to PNG format
   - Applies size constraints (2048x2048 max)
5. **Security Checks**:
   - Detects encrypted PDFs
   - Checks password protection
   - Handles corrupted PDFs gracefully

#### PDF-Specific Processing:
- Only first page converted by default
- Multi-page support available but not used in upload flow
- No JavaScript execution
- No embedded file extraction

### 5. **Error Handling and Recovery**

#### File Processing Exceptions:
- `UnsupportedFileTypeError`: Unknown file type
- `CorruptedFileError`: Invalid file structure
- `FileProcessingError`: Base exception for all file errors

#### Graceful Degradation:
- PDF conversion failures logged but don't crash
- Continues processing other pages if multi-page fails
- Returns meaningful error messages to user

## Pre-Gemini Processing Summary

### What Happens:
1. **File Type Detection**: Magic bytes verification
2. **Size Validation**: 100 bytes to 50MB
3. **Format Validation**: Type-specific checks
4. **PDF → PNG Conversion**: If PDF, converts to image
5. **Image Resizing**: If > 2048x2048, thumbnail created
6. **Base64 Encoding**: Final preparation for API

### What Doesn't Happen:
1. **No Content Filtering**: Receipt content not analyzed
2. **No Text Preprocessing**: OCR handled by Gemini
3. **No Security Scanning**: No malware/virus checks
4. **No Privacy Filtering**: Sensitive data not redacted
5. **No EXIF Stripping**: Metadata preserved
6. **No Format Conversion**: Images stay in original format (except PDF)

## Security Considerations

### Potential Risks:
1. **Large File DoS**: Mitigated by 50MB limit
2. **Malformed Files**: Caught by PIL/PyMuPDF validation
3. **Memory Exhaustion**: In-memory processing with size limits
4. **Malicious PDFs**: PyMuPDF doesn't execute JavaScript
5. **EXIF Data**: Location/camera data preserved (not stripped)

### Recommendations:
1. Consider adding EXIF stripping for privacy
2. Implement virus scanning for uploaded files
3. Add configurable size limits per deployment
4. Consider watermarking or format normalization
5. Add rate limiting for file processing

## File Processing Flow Example

```
1. User uploads IMG_7597.HEIC
   ↓
2. CLI validates file extension → FAILS (HEIC not supported)
   ↓
3. Error: "Unsupported file format '.heic'"

Alternative flow with JPEG:
1. User uploads receipt.jpg
   ↓
2. CLI validates: exists, readable, ≤10MB, .jpg extension
   ↓
3. FileProcessor: Detects JPEG magic bytes
   ↓
4. Validates size (100B < size < 50MB)
   ↓
5. PIL opens image, validates structure
   ↓
6. If > 2048x2048, creates thumbnail
   ↓
7. Base64 encodes image
   ↓
8. Sends to Gemini AI for extraction
```

This sanitization approach prioritizes functionality and performance over security, making it suitable for trusted environments but requiring additional hardening for public-facing deployments.
