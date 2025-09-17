#!/usr/bin/env python3
"""Test PDF to image conversion functionality using PyMuPDF."""

from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quickexpense.services.pdf_converter import PDFConverterService


def read_pdf_file(pdf_path: str) -> bytes:
    """Read PDF file synchronously."""
    with open(pdf_path, "rb") as f:  # noqa: ASYNC230
        return f.read()


def save_image_file(output_path: Path, image_data: bytes) -> None:
    """Save image file synchronously."""
    with open(output_path, "wb") as f:  # noqa: ASYNC230
        f.write(image_data)


async def test_pdf_conversion(pdf_path: str) -> None:
    """Test converting a PDF to image."""
    converter = PDFConverterService()

    # Read PDF file
    pdf_bytes = read_pdf_file(pdf_path)
    pdf_base64 = base64.b64encode(pdf_bytes).decode()

    # Validate PDF
    print(f"Validating PDF: {pdf_path}")  # noqa: T201
    is_valid = await converter.validate_pdf(pdf_base64)
    print(f"  Valid: {is_valid}")  # noqa: T201

    if not is_valid:
        print("  PDF is not valid!")  # noqa: T201
        return

    # Get page count
    page_count = await converter.get_pdf_page_count(pdf_base64)
    print(f"  Pages: {page_count}")  # noqa: T201

    # Get metadata
    metadata = await converter.extract_pdf_metadata(pdf_base64)
    print(f"  Metadata: {metadata}")  # noqa: T201

    # Convert first page to image
    print("\nConverting first page to PNG...")  # noqa: T201
    try:
        image_base64 = await converter.convert_pdf_to_image(pdf_base64, page=0)

        # Save the converted image
        output_path = Path(pdf_path).with_suffix(".png")
        save_image_file(output_path, base64.b64decode(image_base64))

        print(f"  Saved to: {output_path}")  # noqa: T201
        print(f"  Image size: {len(image_base64)} bytes (base64)")  # noqa: T201

    except Exception as e:
        print(f"  Error: {e}")  # noqa: T201


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python test_pdf_conversion.py <pdf_file>")  # noqa: T201
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")  # noqa: T201
        sys.exit(1)

    asyncio.run(test_pdf_conversion(pdf_path))


if __name__ == "__main__":
    main()
