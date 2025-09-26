"""Universal file processing infrastructure for various receipt formats."""

from __future__ import annotations

import base64
import logging
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    _heic_support = True
except ImportError:
    _heic_support = False

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
    HEIC = "heic"
    HEIF = "heif"
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
            "image/heic": cls.HEIC,
            "image/heif": cls.HEIF,
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
            self.HEIC,
            self.HEIF,
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


class UnsupportedFileTypeError(FileProcessingError):
    """Raised when file type is not supported."""


class CorruptedFileError(FileProcessingError):
    """Raised when file is corrupted or unreadable."""


class FileProcessorService:
    """Service for detecting and processing various file types."""

    # Constants
    MIN_FILE_SIZE = 100  # Minimum file size in bytes
    MAX_FILE_SIZE = 50 * 1024 * 1024  # Maximum file size (50MB)

    # Magic bytes for file type detection
    MAGIC_BYTES: ClassVar[dict[bytes, FileType]] = {
        b"\xff\xd8\xff": FileType.JPEG,
        b"\x89PNG\r\n\x1a\n": FileType.PNG,
        b"GIF87a": FileType.GIF,
        b"GIF89a": FileType.GIF,
        b"BM": FileType.BMP,
        b"RIFF": FileType.WEBP,  # Needs additional check
        b"%PDF": FileType.PDF,
        # HEIC files have variable ftyp box positions, handled separately
    }

    def __init__(self) -> None:
        """Initialize file processor service."""
        self._pdf_converter: Any = None

    @property
    def pdf_converter(self) -> Any:  # noqa: ANN401
        """Lazy load PDF converter to avoid circular imports."""
        if self._pdf_converter is None:
            # Import here to avoid circular import issues
            from .pdf_converter import PDFConverterService

            self._pdf_converter = PDFConverterService()
        return self._pdf_converter

    def detect_file_type(self, file_content: bytes | str) -> FileType:
        """Detect file type from content using magic bytes."""
        # Convert string content to bytes
        file_bytes = self._normalize_file_content(file_content)
        if file_bytes is None:
            return FileType.UNKNOWN

        # Check standard magic bytes
        standard_type = self._check_magic_bytes(file_bytes)
        if standard_type != FileType.UNKNOWN:
            return standard_type

        # Check HEIC/HEIF formats
        return self._check_heic_heif_formats(file_bytes)

    def _normalize_file_content(self, file_content: bytes | str) -> bytes | None:
        """Convert file content to bytes format."""
        if isinstance(file_content, bytes):
            return file_content
        try:
            return base64.b64decode(file_content)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to decode base64 content")
            return None

    def _check_magic_bytes(self, file_bytes: bytes) -> FileType:
        """Check standard magic bytes for file type detection."""
        for magic, file_type in self.MAGIC_BYTES.items():
            if file_bytes.startswith(magic):
                # Special case for WEBP
                if magic == b"RIFF" and b"WEBP" in file_bytes[:20]:
                    return FileType.WEBP
                return file_type
        return FileType.UNKNOWN

    def _check_heic_heif_formats(self, file_bytes: bytes) -> FileType:
        """Check for HEIC/HEIF format variations."""
        min_heic_size = 12
        if len(file_bytes) < min_heic_size:
            return FileType.UNKNOWN

        # Check for 'ftyp' box at offset 4
        if file_bytes[4:8] == b"ftyp":
            return self._check_ftyp_brand(file_bytes[8:12])

        # Check for alternative HEIC patterns
        if b"ftypheic" in file_bytes[:40] or b"ftypmif1" in file_bytes[:40]:
            return FileType.HEIC

        return FileType.UNKNOWN

    def _check_ftyp_brand(self, brand: bytes) -> FileType:
        """Check the brand in ftyp box to determine HEIC/HEIF type."""
        if brand in (b"heic", b"heix", b"hevc", b"hevx"):
            return FileType.HEIC
        if brand in (b"heif", b"heim", b"heis", b"hevm", b"hevs"):
            return FileType.HEIF
        return FileType.UNKNOWN

    def validate_file(self, file_content: bytes | str, file_type: FileType) -> bool:
        """Validate file content matches expected type and is not corrupted."""
        if isinstance(file_content, str):
            try:
                file_bytes = base64.b64decode(file_content)
            except Exception:  # noqa: BLE001
                return False
        else:
            file_bytes = file_content

        # Basic size validation
        if len(file_bytes) < self.MIN_FILE_SIZE:  # Too small to be a valid receipt
            return False

        if len(file_bytes) > self.MAX_FILE_SIZE:  # Larger than 50MB
            return False

        # Type-specific validation
        detected_type = self.detect_file_type(file_bytes)
        return not (file_type not in (FileType.UNKNOWN, detected_type))

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
            page_count = await self.pdf_converter.get_pdf_page_count(pdf_base64)
            processing_metadata["pdf_pages"] = page_count
        # Images can be processed directly
        elif content_is_base64:
            processed_content = file_content
        else:
            processed_content = base64.b64encode(file_bytes).decode()

        return ProcessedFile(
            content=str(processed_content),
            file_type=file_type,
            original_file_type=original_file_type,
            processing_metadata=processing_metadata,
        )

    def get_supported_extensions(self) -> set[str]:
        """Get set of supported file extensions."""
        extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".pdf",
        }
        if _heic_support:
            extensions.update({".heic", ".heif"})
        return extensions

    def is_supported_file(self, filename: str) -> bool:
        """Check if file extension is supported."""
        ext = Path(filename).suffix.lower()
        return ext in self.get_supported_extensions()
