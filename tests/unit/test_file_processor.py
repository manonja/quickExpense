"""Tests for the universal file processor service."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest

from quickexpense.services.file_processor import (
    CorruptedFileError,
    FileProcessorService,
    FileType,
    ProcessedFile,
    UnsupportedFileTypeError,
)


class TestFileType:
    """Tests for FileType enum."""

    def test_from_mime_type(self):
        """Test converting MIME types to FileType."""
        assert FileType.from_mime_type("image/jpeg") == FileType.JPEG
        assert FileType.from_mime_type("image/png") == FileType.PNG
        assert FileType.from_mime_type("application/pdf") == FileType.PDF
        assert FileType.from_mime_type("unknown/type") == FileType.UNKNOWN

    def test_from_extension(self):
        """Test converting extensions to FileType."""
        assert FileType.from_extension(".jpg") == FileType.JPG
        assert FileType.from_extension("jpeg") == FileType.JPEG
        assert FileType.from_extension(".PDF") == FileType.PDF
        assert FileType.from_extension(".xyz") == FileType.UNKNOWN

    def test_is_image(self):
        """Test image type detection."""
        assert FileType.JPEG.is_image
        assert FileType.PNG.is_image
        assert FileType.GIF.is_image
        assert not FileType.PDF.is_image
        assert not FileType.UNKNOWN.is_image

    def test_is_pdf(self):
        """Test PDF type detection."""
        assert FileType.PDF.is_pdf
        assert not FileType.JPEG.is_pdf
        assert not FileType.UNKNOWN.is_pdf


class TestFileProcessorService:
    """Tests for FileProcessorService."""

    @pytest.fixture
    def service(self):
        """Create a FileProcessorService instance."""
        return FileProcessorService()

    def test_detect_file_type_jpeg(self, service):
        """Test JPEG file type detection."""
        jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
        assert service.detect_file_type(jpeg_bytes) == FileType.JPEG

    def test_detect_file_type_png(self, service):
        """Test PNG file type detection."""
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        assert service.detect_file_type(png_bytes) == FileType.PNG

    def test_detect_file_type_pdf(self, service):
        """Test PDF file type detection."""
        pdf_bytes = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3"
        assert service.detect_file_type(pdf_bytes) == FileType.PDF

    def test_detect_file_type_base64(self, service):
        """Test file type detection from base64."""
        jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
        jpeg_base64 = base64.b64encode(jpeg_bytes).decode()
        assert service.detect_file_type(jpeg_base64) == FileType.JPEG

    def test_detect_file_type_unknown(self, service):
        """Test unknown file type detection."""
        unknown_bytes = b"Unknown file format"
        assert service.detect_file_type(unknown_bytes) == FileType.UNKNOWN

    def test_validate_file_valid(self, service):
        """Test validating a valid file."""
        # Create a valid JPEG with sufficient size
        jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 200
        assert service.validate_file(jpeg_bytes, FileType.JPEG)

    def test_validate_file_too_small(self, service):
        """Test validating a file that's too small."""
        small_bytes = b"tiny"
        assert not service.validate_file(small_bytes, FileType.JPEG)

    def test_validate_file_too_large(self, service):
        """Test validating a file that's too large."""
        large_bytes = b"\xFF\xD8\xFF" + b"\x00" * (51 * 1024 * 1024)
        assert not service.validate_file(large_bytes, FileType.JPEG)

    def test_validate_file_type_mismatch(self, service):
        """Test validating a file with mismatched type."""
        jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 200
        assert not service.validate_file(jpeg_bytes, FileType.PNG)

    @pytest.mark.asyncio
    async def test_process_file_image(self, service):
        """Test processing an image file."""
        jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 200
        jpeg_base64 = base64.b64encode(jpeg_bytes).decode()

        result = await service.process_file(jpeg_base64, FileType.JPEG)

        assert isinstance(result, ProcessedFile)
        assert result.file_type == FileType.JPEG
        assert result.original_file_type == FileType.JPEG
        assert result.content == jpeg_base64

    @pytest.mark.asyncio
    async def test_process_file_pdf(self, service):
        """Test processing a PDF file."""
        pdf_bytes = b"%PDF-1.4\n" + b"\x00" * 200
        pdf_base64 = base64.b64encode(pdf_bytes).decode()

        # Mock the PDF converter
        mock_converter = AsyncMock()
        mock_converter.convert_pdf_to_image.return_value = "converted_image_base64"
        mock_converter.get_pdf_page_count.return_value = 1

        # Mock the _pdf_converter attribute directly
        service._pdf_converter = mock_converter
        
        result = await service.process_file(pdf_base64, FileType.PDF)

        assert isinstance(result, ProcessedFile)
        assert result.file_type == FileType.PNG  # Converted to PNG
        assert result.original_file_type == FileType.PDF
        assert result.content == "converted_image_base64"
        assert result.processing_metadata["conversion"] == "pdf_to_png"
        assert result.processing_metadata["pdf_pages"] == 1

    @pytest.mark.asyncio
    async def test_process_file_auto_detect(self, service):
        """Test processing a file with auto-detection."""
        jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 200
        result = await service.process_file(jpeg_bytes)

        assert result.file_type == FileType.JPEG
        assert result.original_file_type == FileType.JPEG

    @pytest.mark.asyncio
    async def test_process_file_unknown_type(self, service):
        """Test processing an unknown file type."""
        unknown_bytes = b"Unknown format" + b"\x00" * 200

        with pytest.raises(UnsupportedFileTypeError):
            await service.process_file(unknown_bytes)

    @pytest.mark.asyncio
    async def test_process_file_corrupted(self, service):
        """Test processing a corrupted file."""
        # Too small to be valid
        small_bytes = b"tiny"

        with pytest.raises(CorruptedFileError):
            await service.process_file(small_bytes, FileType.JPEG)

    @pytest.mark.asyncio
    async def test_process_file_invalid_base64(self, service):
        """Test processing invalid base64 content."""
        invalid_base64 = "not-valid-base64!"

        with pytest.raises(CorruptedFileError):
            await service.process_file(invalid_base64)

    def test_get_supported_extensions(self, service):
        """Test getting supported extensions."""
        extensions = service.get_supported_extensions()
        assert ".jpg" in extensions
        assert ".pdf" in extensions
        assert len(extensions) == 7  # 6 image formats + PDF

    def test_is_supported_file(self, service):
        """Test checking if file is supported."""
        assert service.is_supported_file("receipt.jpg")
        assert service.is_supported_file("document.PDF")
        assert service.is_supported_file("image.png")
        assert not service.is_supported_file("data.txt")
        assert not service.is_supported_file("video.mp4")