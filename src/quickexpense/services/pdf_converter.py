"""PDF to image conversion service using PyMuPDF (fitz)."""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

try:
    import fitz  # PyMuPDF

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

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
                "PDF support not available. Install with: pip install pymupdf"
            )

    def _ensure_pdf_support(self) -> None:
        """Check if PDF support is available."""
        if not PDF_SUPPORT:
            msg = "PDF support not installed. Install with: pip install pymupdf"
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
            ImportError: If PyMuPDF not installed
        """
        self._ensure_pdf_support()

        if dpi is None:
            dpi = self.DEFAULT_DPI

        try:
            # Decode PDF
            pdf_bytes = base64.b64decode(pdf_base64)

            # Open PDF with PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            if len(doc) == 0:
                msg = "PDF contains no pages"
                raise ValueError(msg)

            if page >= len(doc):
                msg = f"Page {page} does not exist (PDF has {len(doc)} pages)"
                raise ValueError(msg)

            # Get the page
            pdf_page = doc[page]

            # Calculate matrix for desired DPI
            # PyMuPDF default is 72 DPI, so scale factor = desired_dpi / 72
            scale = dpi / 72.0
            matrix = fitz.Matrix(scale, scale)

            # Render page to pixmap
            pixmap = pdf_page.get_pixmap(matrix=matrix)

            # Convert to PIL Image
            img_data = pixmap.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            # Resize if too large while maintaining aspect ratio
            image.thumbnail(self.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

            # Convert to PNG
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            buffer.seek(0)

            # Close resources
            doc.close()

            # Return base64 encoded
            return base64.b64encode(buffer.read()).decode()

        except Exception as e:
            logger.error("PDF conversion failed: %s", e)
            if "fitz" in str(type(e)):
                msg = f"PyMuPDF error: {e}"
                raise ValueError(msg) from e
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

            # Try to open with PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Check basic properties
            if len(doc) == 0:
                doc.close()
                return False

            # Try to access first page
            _ = doc[0]
            doc.close()

            return True
        except Exception as e:  # noqa: BLE001
            logger.debug("PDF validation failed: %s", e)
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
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()
            return page_count
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
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Extract metadata
            metadata = doc.metadata
            metadata["page_count"] = len(doc)
            metadata["is_encrypted"] = doc.is_encrypted
            metadata["needs_pass"] = doc.needs_pass

            # Add page information
            if len(doc) > 0:
                first_page = doc[0]
                metadata["page_width"] = first_page.rect.width
                metadata["page_height"] = first_page.rect.height

            doc.close()
            return metadata

        except Exception as e:  # noqa: BLE001
            logger.error("Failed to extract PDF metadata: %s", e)
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

        page_count = await self.get_pdf_page_count(pdf_base64)
        images = []

        for page in range(page_count):
            try:
                image_base64 = await self.convert_pdf_to_image(pdf_base64, page, dpi)
                images.append(image_base64)
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to convert page %s: %s", page, e)
                # Continue with other pages

        return images
