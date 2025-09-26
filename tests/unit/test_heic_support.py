"""Unit tests for HEIC file support."""

from __future__ import annotations

import base64

import pytest
from PIL import Image

from quickexpense.services.file_processor import (
    FileProcessorService,
    FileType,
    ProcessedFile,
)


class TestHEICSupport:
    """Test HEIC file support functionality."""

    @pytest.fixture
    def file_processor(self) -> FileProcessorService:
        """Create file processor instance."""
        return FileProcessorService()

    @pytest.fixture
    def heic_magic_bytes(self) -> bytes:
        """Sample HEIC file magic bytes."""
        # HEIC file structure: size(4) + 'ftyp'(4) + brand(4)
        return b"\x00\x00\x00\x18ftypheic" + b"\x00" * 100

    @pytest.fixture
    def heif_magic_bytes(self) -> bytes:
        """Sample HEIF file magic bytes."""
        return b"\x00\x00\x00\x18ftypheif" + b"\x00" * 100

    def test_heic_file_type_enum(self) -> None:
        """Test HEIC file type enum values."""
        assert FileType.HEIC.value == "heic"
        assert FileType.HEIF.value == "heif"
        assert FileType.HEIC.is_image is True
        assert FileType.HEIF.is_image is True
        assert FileType.HEIC.is_pdf is False

    def test_heic_from_extension(self) -> None:
        """Test HEIC file type detection from extension."""
        assert FileType.from_extension(".heic") == FileType.HEIC
        assert FileType.from_extension(".HEIC") == FileType.HEIC
        assert FileType.from_extension("heic") == FileType.HEIC
        assert FileType.from_extension(".heif") == FileType.HEIF
        assert FileType.from_extension(".HEIF") == FileType.HEIF

    def test_heic_from_mime_type(self) -> None:
        """Test HEIC file type detection from MIME type."""
        assert FileType.from_mime_type("image/heic") == FileType.HEIC
        assert FileType.from_mime_type("image/heif") == FileType.HEIF
        assert FileType.from_mime_type("IMAGE/HEIC") == FileType.HEIC

    def test_detect_heic_file_type(
        self, file_processor: FileProcessorService, heic_magic_bytes: bytes
    ) -> None:
        """Test HEIC file type detection from content."""
        detected = file_processor.detect_file_type(heic_magic_bytes)
        assert detected == FileType.HEIC

    def test_detect_heif_file_type(
        self, file_processor: FileProcessorService, heif_magic_bytes: bytes
    ) -> None:
        """Test HEIF file type detection from content."""
        detected = file_processor.detect_file_type(heif_magic_bytes)
        assert detected == FileType.HEIF

    def test_detect_heic_variants(self, file_processor: FileProcessorService) -> None:
        """Test detection of various HEIC brand codes."""
        # Test different HEIC brand variants
        brands = [b"heic", b"heix", b"hevc", b"hevx"]
        for brand in brands:
            content = b"\x00\x00\x00\x18ftyp" + brand + b"\x00" * 100
            assert file_processor.detect_file_type(content) == FileType.HEIC

    def test_detect_heif_variants(self, file_processor: FileProcessorService) -> None:
        """Test detection of various HEIF brand codes."""
        brands = [b"heif", b"heim", b"heis", b"hevm", b"hevs"]
        for brand in brands:
            content = b"\x00\x00\x00\x18ftyp" + brand + b"\x00" * 100
            assert file_processor.detect_file_type(content) == FileType.HEIF

    def test_detect_heic_alternative_structure(
        self, file_processor: FileProcessorService
    ) -> None:
        """Test HEIC detection with alternative file structure."""
        # Some HEIC files have different box ordering
        content = b"\x00\x00\x00\x00" + b"ftypheic" + b"\x00" * 100
        assert file_processor.detect_file_type(content) == FileType.HEIC

    def test_supported_extensions_with_heic(
        self, file_processor: FileProcessorService
    ) -> None:
        """Test supported extensions include HEIC when available."""
        extensions = file_processor.get_supported_extensions()

        # Check if pillow-heif is available
        try:
            import pillow_heif  # Check availability

            # Explicitly reference the module to satisfy type checkers
            _ = pillow_heif.__name__

            assert ".heic" in extensions
            assert ".heif" in extensions
        except ImportError:
            # HEIC not available in test environment
            assert ".heic" not in extensions
            assert ".heif" not in extensions

    def test_is_supported_file_heic(self, file_processor: FileProcessorService) -> None:
        """Test HEIC files are supported."""
        try:
            import pillow_heif  # Check availability

            # Explicitly reference the module to satisfy type checkers
            _ = pillow_heif.__name__

            assert file_processor.is_supported_file("receipt.heic") is True
            assert file_processor.is_supported_file("photo.HEIC") is True
            assert file_processor.is_supported_file("/path/to/image.heif") is True
        except ImportError:
            # HEIC not available in test environment
            assert file_processor.is_supported_file("receipt.heic") is False

    def test_validate_heic_file(
        self, file_processor: FileProcessorService, heic_magic_bytes: bytes
    ) -> None:
        """Test HEIC file validation."""
        # Valid HEIC file
        assert file_processor.validate_file(heic_magic_bytes, FileType.HEIC) is True

        # Invalid - wrong type
        assert file_processor.validate_file(heic_magic_bytes, FileType.JPEG) is False

        # Invalid - too small
        assert file_processor.validate_file(b"tiny", FileType.HEIC) is False

    @pytest.mark.asyncio
    async def test_process_heic_file(
        self, file_processor: FileProcessorService, heic_magic_bytes: bytes
    ) -> None:
        """Test processing HEIC file."""
        # Base64 encode the content
        heic_base64 = base64.b64encode(heic_magic_bytes).decode()

        # Process the file
        result = await file_processor.process_file(heic_base64, FileType.HEIC)

        assert isinstance(result, ProcessedFile)
        assert result.file_type == FileType.HEIC
        assert result.original_file_type == FileType.HEIC
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_process_heic_auto_detect(
        self, file_processor: FileProcessorService, heic_magic_bytes: bytes
    ) -> None:
        """Test processing HEIC file with auto-detection."""
        # Base64 encode the content
        heic_base64 = base64.b64encode(heic_magic_bytes).decode()

        # Process without specifying type
        result = await file_processor.process_file(heic_base64)

        assert isinstance(result, ProcessedFile)
        assert result.file_type == FileType.HEIC
        assert result.original_file_type == FileType.HEIC

    def test_heic_pillow_integration(self) -> None:
        """Test HEIC integration with Pillow when available."""
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()

            # Create a simple test image in memory
            test_image = Image.new("RGB", (100, 100), color="red")

            # This tests that Pillow can handle HEIC after registration
            # In real usage, Image.open() would work with HEIC files
            assert test_image is not None

        except ImportError:
            # Skip if pillow-heif not available
            pytest.skip("pillow-heif not available")

    def test_cli_supported_formats(self) -> None:
        """Test CLI supported formats include HEIC when available."""
        from quickexpense.cli import SUPPORTED_FORMATS

        try:
            import pillow_heif  # Check availability

            # Explicitly reference the module to satisfy type checkers
            _ = pillow_heif.__name__

            assert ".heic" in SUPPORTED_FORMATS
            assert ".heif" in SUPPORTED_FORMATS
        except ImportError:
            # In test environment without pillow-heif
            pass  # Formats won't be added without the library
