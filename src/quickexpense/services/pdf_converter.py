"""PDF to image conversion service using pdf2image."""

from __future__ import annotations

import base64
import io
import logging
import tempfile
from pathlib import Path
from typing import Any

try:
    from pdf2image import convert_from_bytes
    from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
    from pypdf import PdfReader

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    PDFPageCountError = Exception
    PDFSyntaxError = Exception

from PIL import Image

logger = logging.getLogger(__name__)


class PDFConverterService:
    """Service for converting PDF files to images for AI processing."""

    DEFAULT_DPI = 300  # High quality for OCR
    MAX_IMAGE_SIZE = (2048, 2048)  # Max size for AI processing
    JPEG_QUALITY = 95

    def __init__(self) -> None:
        """Initialize PDF converter service."""
        if not PDF_SUPPORT:
            logger.warning(
                "PDF support not available. Install with: pip install pdf2image pypdf"
            )

    def _ensure_pdf_support(self) -> None:
        """Check if PDF support is available."""
        if not PDF_SUPPORT:
            msg = "PDF support not installed. Install with: pip install pdf2image pypdf"
            raise ImportError(msg)

    async def convert_pdf_to_image(
        self, pdf_base64: str, page: int = 0, dpi: int | None = None
    ) -> str:
        """Convert PDF page to high-quality PNG image.

        Args:
            pdf_base64: Base64 encoded PDF content
            page: Page number to convert (0-indexed)
            dpi: DPI for conversion (default: 300)

        Returns:
            Base64 encoded PNG image

        Raises:
            ValueError: If PDF is invalid or page doesn't exist
            ImportError: If PDF libraries not installed
        """
        self._ensure_pdf_support()

        if dpi is None:
            dpi = self.DEFAULT_DPI

        try:
            # Decode PDF
            pdf_bytes = base64.b64decode(pdf_base64)

            # Convert PDF to images
            images = convert_from_bytes(
                pdf_bytes,
                dpi=dpi,
                first_page=page + 1,  # pdf2image uses 1-based indexing
                last_page=page + 1,
            )

            if not images:
                msg = f"No image generated for page {page}"
                raise ValueError(msg)

            image = images[0]

            # Resize if too large while maintaining aspect ratio
            image.thumbnail(self.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

            # Convert to PNG
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            buffer.seek(0)

            # Return base64 encoded
            return base64.b64encode(buffer.read()).decode()

        except PDFPageCountError as e:
            msg = f"Invalid page number {page}"
            raise ValueError(msg) from e
        except PDFSyntaxError as e:
            msg = "Invalid or corrupted PDF file"
            raise ValueError(msg) from e
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise

    async def validate_pdf(self, pdf_base64: str) -> bool:
        """Validate PDF format and readability.

        Args:
            pdf_base64: Base64 encoded PDF content

        Returns:
            True if PDF is valid and readable
        """
        self._ensure_pdf_support()

        try:
            pdf_bytes = base64.b64decode(pdf_base64)

            # Try to read with pypdf
            reader = PdfReader(io.BytesIO(pdf_bytes))

            # Check basic properties
            if len(reader.pages) == 0:
                return False

            # Try to access first page
            _ = reader.pages[0]

            return True
        except Exception as e:
            logger.debug(f"PDF validation failed: {e}")
            return False

    async def get_pdf_page_count(self, pdf_base64: str) -> int:
        """Get number of pages in PDF.

        Args:
            pdf_base64: Base64 encoded PDF content

        Returns:
            Number of pages in the PDF

        Raises:
            ValueError: If PDF is invalid
        """
        self._ensure_pdf_support()

        try:
            pdf_bytes = base64.b64decode(pdf_base64)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return len(reader.pages)
        except Exception as e:
            msg = f"Failed to read PDF: {e}"
            raise ValueError(msg) from e

    async def extract_pdf_metadata(self, pdf_base64: str) -> dict[str, Any]:
        """Extract metadata from PDF.

        Args:
            pdf_base64: Base64 encoded PDF content

        Returns:
            Dictionary containing PDF metadata
        """
        self._ensure_pdf_support()

        try:
            pdf_bytes = base64.b64decode(pdf_base64)
            reader = PdfReader(io.BytesIO(pdf_bytes))

            metadata = {}
            if reader.metadata:
                # Extract common metadata fields
                for key, value in reader.metadata.items():
                    if key.startswith("/"):
                        key = key[1:]  # Remove leading slash
                    metadata[key] = str(value) if value else None

            metadata["page_count"] = len(reader.pages)
            metadata["is_encrypted"] = reader.is_encrypted

            return metadata
        except Exception as e:
            logger.error(f"Failed to extract PDF metadata: {e}")
            return {"error": str(e)}

    async def convert_pdf_all_pages(
        self, pdf_base64: str, dpi: int | None = None
    ) -> list[str]:
        """Convert all PDF pages to images.

        Args:
            pdf_base64: Base64 encoded PDF content
            dpi: DPI for conversion (default: 300)

        Returns:
            List of base64 encoded PNG images
        """
        self._ensure_pdf_support()

        if dpi is None:
            dpi = self.DEFAULT_DPI

        page_count = await self.get_pdf_page_count(pdf_base64)
        images = []

        for page in range(page_count):
            try:
                image_base64 = await self.convert_pdf_to_image(pdf_base64, page, dpi)
                images.append(image_base64)
            except Exception as e:
                logger.error(f"Failed to convert page {page}: {e}")
                # Continue with other pages

        return images