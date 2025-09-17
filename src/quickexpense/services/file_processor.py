"""Universal file processing infrastructure for various receipt formats."""

from __future__ import annotations

import base64
import io
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FileType(str, Enum):
    """Supported file types for receipt processing."""

    JPEG = "jpeg"
    JPG = "jpg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    WEBP = "webp"
    PDF = "pdf"
    UNKNOWN = "unknown"

    @classmethod
    def from_mime_type(cls, mime_type: str) -> FileType:
        """Convert MIME type to FileType enum."""
        mime_mapping = {
            "image/jpeg": cls.JPEG,
            "image/jpg": cls.JPG,
            "image/png": cls.PNG,
            "image/gif": cls.GIF,
            "image/bmp": cls.BMP,
            "image/webp": cls.WEBP,
            "application/pdf": cls.PDF,
        }
        return mime_mapping.get(mime_type.lower(), cls.UNKNOWN)

    @classmethod
    def from_extension(cls, extension: str) -> FileType:
        """Convert file extension to FileType enum."""
        ext = extension.lower().lstrip(".")
        try:
            return cls(ext)
        except ValueError:
            return cls.UNKNOWN

    @property
    def is_image(self) -> bool:
        """Check if file type is an image format."""
        return self in {
            self.JPEG,
            self.JPG,
            self.PNG,
            self.GIF,
            self.BMP,
            self.WEBP,
        }

    @property
    def is_pdf(self) -> bool:
        """Check if file type is PDF."""
        return self == self.PDF


class ProcessedFile(BaseModel):
    """Processed file ready for AI extraction."""

    content: str = Field(..., min_length=1)
    file_type: FileType
    original_file_type: FileType
    processing_metadata: dict[str, Any] = Field(default_factory=dict)


class FileProcessingError(Exception):
    """Base exception for file processing errors."""

    pass


class UnsupportedFileTypeError(FileProcessingError):
    """Raised when file type is not supported."""

    pass


class CorruptedFileError(FileProcessingError):
    """Raised when file is corrupted or unreadable."""

    pass


class FileProcessorService:
    """Service for detecting and processing various file types."""

    # Magic bytes for file type detection
    MAGIC_BYTES = {
        b"\xFF\xD8\xFF": FileType.JPEG,
        b"\x89PNG\r\n\x1a\n": FileType.PNG,
        b"GIF87a": FileType.GIF,
        b"GIF89a": FileType.GIF,
        b"BM": FileType.BMP,
        b"RIFF": FileType.WEBP,  # Needs additional check
        b"%PDF": FileType.PDF,
    }

    def __init__(self) -> None:
        """Initialize file processor service."""
        self._pdf_converter = None

    @property
    def pdf_converter(self) -> Any:
        """Lazy load PDF converter to avoid circular imports."""
        if self._pdf_converter is None:
            from .pdf_converter import PDFConverterService

            self._pdf_converter = PDFConverterService()
        return self._pdf_converter

    def detect_file_type(self, file_content: bytes | str) -> FileType:
        """Detect file type from content using magic bytes."""
        if isinstance(file_content, str):
            # Assume base64 encoded
            try:
                file_content = base64.b64decode(file_content)
            except Exception:
                logger.warning("Failed to decode base64 content")
                return FileType.UNKNOWN

        # Check magic bytes
        for magic, file_type in self.MAGIC_BYTES.items():
            if file_content.startswith(magic):
                # Special case for WEBP
                if magic == b"RIFF" and b"WEBP" in file_content[:20]:
                    return FileType.WEBP
                return file_type

        return FileType.UNKNOWN

    def validate_file(self, file_content: bytes | str, file_type: FileType) -> bool:
        """Validate file content matches expected type and is not corrupted."""
        if isinstance(file_content, str):
            try:
                file_bytes = base64.b64decode(file_content)
            except Exception:
                return False
        else:
            file_bytes = file_content

        # Basic size validation
        if len(file_bytes) < 100:  # Too small to be a valid receipt
            return False

        if len(file_bytes) > 50 * 1024 * 1024:  # Larger than 50MB
            return False

        # Type-specific validation
        detected_type = self.detect_file_type(file_bytes)
        if file_type != FileType.UNKNOWN and detected_type != file_type:
            return False

        return True

    async def process_file(
        self, file_content: str | bytes, file_type: FileType | None = None
    ) -> ProcessedFile:
        """Process file into format ready for AI extraction."""
        # Ensure we have bytes
        if isinstance(file_content, str):
            try:
                file_bytes = base64.b64decode(file_content)
                content_is_base64 = True
            except Exception as e:
                raise CorruptedFileError(f"Invalid base64 content: {e}") from e
        else:
            file_bytes = file_content
            content_is_base64 = False

        # Detect file type if not provided
        if file_type is None:
            file_type = self.detect_file_type(file_bytes)

        if file_type == FileType.UNKNOWN:
            raise UnsupportedFileTypeError("Unable to detect file type")

        # Validate file
        if not self.validate_file(file_bytes, file_type):
            raise CorruptedFileError(f"Invalid or corrupted {file_type.value} file")

        # Process based on type
        original_file_type = file_type
        processing_metadata = {"original_format": file_type.value}

        if file_type.is_pdf:
            # Convert PDF to image
            logger.info("Converting PDF to image for processing")
            if content_is_base64:
                pdf_base64 = file_content
            else:
                pdf_base64 = base64.b64encode(file_bytes).decode()

            image_base64 = await self.pdf_converter.convert_pdf_to_image(pdf_base64)
            processed_content = image_base64
            file_type = FileType.PNG  # PDF converter outputs PNG
            processing_metadata["conversion"] = "pdf_to_png"
            processing_metadata["pdf_pages"] = await self.pdf_converter.get_pdf_page_count(
                pdf_base64
            )
        else:
            # Images can be processed directly
            if content_is_base64:
                processed_content = file_content
            else:
                processed_content = base64.b64encode(file_bytes).decode()

        return ProcessedFile(
            content=processed_content,
            file_type=file_type,
            original_file_type=original_file_type,
            processing_metadata=processing_metadata,
        )

    def get_supported_extensions(self) -> set[str]:
        """Get set of supported file extensions."""
        return {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".pdf",
        }

    def is_supported_file(self, filename: str) -> bool:
        """Check if file extension is supported."""
        import os

        ext = os.path.splitext(filename)[1].lower()
        return ext in self.get_supported_extensions()