"""Unit tests for simplified CLI module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from quickexpense.cli import (
    APIError,
    FileValidationError,
    QuickExpenseCLI,
    create_parser,
)
from quickexpense.models import ExtractedReceipt


class TestCLIArgumentParsing:
    """Test CLI argument parsing."""

    def test_create_parser(self) -> None:
        """Test parser creation."""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_upload_command_basic(self) -> None:
        """Test basic upload command parsing."""
        parser = create_parser()
        args = parser.parse_args(["upload", "receipt.jpeg"])
        assert args.command == "upload"
        assert args.receipt == "receipt.jpeg"
        assert args.dry_run is False
        assert args.output == "text"

    def test_upload_command_with_dry_run(self) -> None:
        """Test upload command with dry-run flag."""
        parser = create_parser()
        args = parser.parse_args(["upload", "receipt.png", "--dry-run"])
        assert args.command == "upload"
        assert args.receipt == "receipt.png"
        assert args.dry_run is True
        assert args.output == "text"

    def test_upload_command_with_json_output(self) -> None:
        """Test upload command with JSON output."""
        parser = create_parser()
        args = parser.parse_args(["upload", "receipt.jpg", "--output", "json"])
        assert args.command == "upload"
        assert args.receipt == "receipt.jpg"
        assert args.dry_run is False
        assert args.output == "json"

    def test_upload_command_all_options(self) -> None:
        """Test upload command with all options."""
        parser = create_parser()
        args = parser.parse_args(
            ["upload", "receipt.webp", "--dry-run", "--output", "json"]
        )
        assert args.command == "upload"
        assert args.receipt == "receipt.webp"
        assert args.dry_run is True
        assert args.output == "json"

    def test_missing_command(self) -> None:
        """Test parser with missing command."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_invalid_command(self) -> None:
        """Test parser with invalid command."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["invalid"])

    def test_invalid_output_format(self) -> None:
        """Test parser with invalid output format."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["upload", "receipt.jpg", "--output", "xml"])


class TestFileValidation:
    """Test file validation functionality."""

    def test_validate_file_success(self, tmp_path: Path) -> None:
        """Test successful file validation."""
        cli = QuickExpenseCLI()
        test_file = tmp_path / "receipt.jpeg"
        test_file.write_text("test")

        # Should not raise
        cli.validate_file(test_file)

    def test_validate_file_not_found(self) -> None:
        """Test validation with non-existent file."""
        cli = QuickExpenseCLI()
        with pytest.raises(FileValidationError, match="File not found"):
            cli.validate_file(Path("/nonexistent/file.jpg"))

    def test_validate_file_is_directory(self, tmp_path: Path) -> None:
        """Test validation with directory instead of file."""
        cli = QuickExpenseCLI()
        with pytest.raises(FileValidationError, match="Not a file"):
            cli.validate_file(tmp_path)

    def test_validate_file_unsupported_format(self, tmp_path: Path) -> None:
        """Test validation with unsupported file format."""
        cli = QuickExpenseCLI()
        test_file = tmp_path / "document.pdf"
        test_file.write_text("test")

        with pytest.raises(FileValidationError, match="Unsupported file format"):
            cli.validate_file(test_file)

    @pytest.mark.parametrize(
        "filename",
        [
            "receipt.jpg",
            "receipt.jpeg",
            "receipt.JPG",
            "receipt.JPEG",
            "receipt.png",
            "receipt.PNG",
            "receipt.gif",
            "receipt.GIF",
            "receipt.bmp",
            "receipt.BMP",
            "receipt.webp",
            "receipt.WEBP",
        ],
    )
    def test_validate_file_supported_formats(
        self, tmp_path: Path, filename: str
    ) -> None:
        """Test validation with all supported formats."""
        cli = QuickExpenseCLI()
        test_file = tmp_path / filename
        test_file.write_text("test")

        # Should not raise
        cli.validate_file(test_file)


class TestOutputFormatting:
    """Test output formatting functionality."""

    @pytest.fixture
    def sample_result(self) -> dict[str, Any]:
        """Sample result data for testing."""
        return {
            "file": "/path/to/receipt.jpg",
            "receipt": {
                "vendor_name": "Starbucks",
                "transaction_date": "2024-01-15",
                "total_amount": "12.50",
                "tax_amount": "1.50",
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Coffee",
                        "total_price": "5.50",
                    },
                    {
                        "description": "Muffin",
                        "total_price": "5.50",
                    },
                ],
            },
            "expense": {
                "category": "Food & Dining",
                "description": "Coffee, Muffin",
                "payment_account": "credit_card",
            },
            "message": "Successfully created expense in QuickBooks (ID: 123)",
        }

    def test_format_output_text(self, sample_result: dict[str, Any]) -> None:
        """Test text output formatting."""
        cli = QuickExpenseCLI()
        output = cli.format_output(sample_result, "text")

        assert "=== Receipt Data ===" in output
        assert "Vendor: Starbucks" in output
        assert "Total Amount: $12.50" in output
        assert "Tax: $1.50" in output
        assert "Coffee ($5.50)" in output
        assert "Muffin ($5.50)" in output
        assert "Category: Food & Dining" in output
        assert "Successfully created expense" in output

    def test_format_output_text_dry_run(self, sample_result: dict[str, Any]) -> None:
        """Test text output formatting in dry-run mode."""
        cli = QuickExpenseCLI()
        sample_result["dry_run"] = True
        output = cli.format_output(sample_result, "text")

        assert "=== DRY RUN MODE ===" in output
        assert "Vendor: Starbucks" in output

    def test_format_output_json(self, sample_result: dict[str, Any]) -> None:
        """Test JSON output formatting."""
        cli = QuickExpenseCLI()
        output = cli.format_output(sample_result, "json")

        # Should be valid JSON
        parsed = json.loads(output)
        assert parsed["receipt"]["vendor_name"] == "Starbucks"
        assert parsed["expense"]["category"] == "Food & Dining"

    def test_format_output_missing_data(self) -> None:
        """Test formatting with missing data."""
        cli = QuickExpenseCLI()
        result = {"file": "test.jpg"}
        output = cli.format_output(result, "text")

        assert "Unknown" in output
        assert "N/A" in output


@pytest.mark.asyncio
class TestServiceInitialization:
    """Test service initialization."""

    @patch("quickexpense.cli.TokenStore")
    @patch("quickexpense.cli.get_settings")
    async def test_initialize_services_no_tokens(
        self, mock_get_settings: Mock, mock_token_store: Mock
    ) -> None:
        """Test initialization when no tokens are found."""
        mock_token_store.return_value.load_tokens.return_value = None

        cli = QuickExpenseCLI()
        with pytest.raises(APIError, match="No authentication tokens found"):
            await cli.initialize_services()

    @patch("quickexpense.cli.TokenStore")
    @patch("quickexpense.cli.get_settings")
    @patch("quickexpense.cli.GeminiService")
    @patch("quickexpense.cli.QuickBooksClient")
    @patch("quickexpense.cli.QuickBooksService")
    async def test_initialize_services_success(
        self,
        mock_qb_service: Mock,
        mock_qb_client: Mock,
        mock_gemini_service: Mock,
        mock_get_settings: Mock,
        mock_token_store: Mock,
    ) -> None:
        """Test successful service initialization."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_model = "test-model"
        mock_settings.gemini_timeout = 30
        mock_settings.qb_base_url = "https://api.test.com"
        mock_get_settings.return_value = mock_settings

        # Mock tokens
        mock_tokens = {
            "access_token": "test-token",
            "refresh_token": "refresh-token",
            "company_id": "test-company",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
        }
        mock_token_store.return_value.load_tokens.return_value = mock_tokens

        cli = QuickExpenseCLI()
        await cli.initialize_services()

        assert cli.gemini_service is not None
        assert cli.quickbooks_service is not None
        assert cli.quickbooks_client is not None


@pytest.mark.asyncio
class TestReceiptProcessing:
    """Test receipt processing functionality."""

    @pytest.fixture
    def mock_cli(self) -> QuickExpenseCLI:
        """Create a CLI instance with mocked services."""
        cli = QuickExpenseCLI()
        cli.gemini_service = MagicMock()
        cli.quickbooks_service = MagicMock()
        # Ensure create_expense is an AsyncMock
        cli.quickbooks_service.create_expense = AsyncMock()
        return cli

    async def test_process_receipt_success(
        self, mock_cli: QuickExpenseCLI, tmp_path: Path
    ) -> None:
        """Test successful receipt processing."""
        # Create test file
        test_file = tmp_path / "receipt.jpg"
        test_file.write_bytes(b"fake image data")

        # Mock receipt data
        mock_receipt = ExtractedReceipt(
            vendor_name="Test Vendor",
            total_amount="10.00",
            transaction_date="2024-01-15",
            currency="USD",
            line_items=[],
            subtotal="10.00",
            tax_amount="0.00",
            vendor_address=None,
            vendor_phone=None,
            receipt_number=None,
            notes=None,
        )
        mock_cli.gemini_service.extract_receipt_data = AsyncMock(
            return_value=mock_receipt
        )

        # Mock QuickBooks response
        mock_cli.quickbooks_service.create_expense = AsyncMock(
            return_value={"Id": "123", "SyncToken": "0"}
        )

        result = await mock_cli.process_receipt(test_file, dry_run=False)

        assert result["receipt"]["vendor_name"] == "Test Vendor"
        assert result["expense"]["vendor_name"] == "Test Vendor"
        assert "quickbooks_response" in result
        assert "Successfully created expense" in result["message"]

    async def test_process_receipt_dry_run(
        self, mock_cli: QuickExpenseCLI, tmp_path: Path
    ) -> None:
        """Test receipt processing in dry-run mode."""
        # Create test file
        test_file = tmp_path / "receipt.jpg"
        test_file.write_bytes(b"fake image data")

        # Mock receipt data
        mock_receipt = ExtractedReceipt(
            vendor_name="Test Vendor",
            total_amount="10.00",
            transaction_date="2024-01-15",
            currency="USD",
            line_items=[],
            subtotal="10.00",
            tax_amount="0.00",
            vendor_address=None,
            vendor_phone=None,
            receipt_number=None,
            notes=None,
        )
        mock_cli.gemini_service.extract_receipt_data = AsyncMock(
            return_value=mock_receipt
        )

        result = await mock_cli.process_receipt(test_file, dry_run=True)

        assert result["receipt"]["vendor_name"] == "Test Vendor"
        assert result["dry_run"] is True
        assert "DRY RUN" in result["message"]
        assert "quickbooks_response" not in result

    async def test_process_receipt_extraction_failure(
        self, mock_cli: QuickExpenseCLI, tmp_path: Path
    ) -> None:
        """Test handling of receipt extraction failure."""
        # Create test file
        test_file = tmp_path / "receipt.jpg"
        test_file.write_bytes(b"fake image data")

        # Mock extraction failure
        mock_cli.gemini_service.extract_receipt_data = AsyncMock(
            side_effect=ValueError("Failed to extract receipt data")
        )

        with pytest.raises(APIError, match="Invalid data format"):
            await mock_cli.process_receipt(test_file, dry_run=False)

    async def test_process_receipt_quickbooks_failure(
        self, mock_cli: QuickExpenseCLI, tmp_path: Path
    ) -> None:
        """Test handling of QuickBooks creation failure."""
        # Create test file
        test_file = tmp_path / "receipt.jpg"
        test_file.write_bytes(b"fake image data")

        # Mock successful extraction
        mock_receipt = ExtractedReceipt(
            vendor_name="Test Vendor",
            total_amount="10.00",
            transaction_date="2024-01-15",
            currency="USD",
            line_items=[],
            subtotal="10.00",
            tax_amount="0.00",
            vendor_address=None,
            vendor_phone=None,
            receipt_number=None,
            notes=None,
        )
        mock_cli.gemini_service.extract_receipt_data = AsyncMock(
            return_value=mock_receipt
        )

        # Mock QuickBooks failure
        mock_cli.quickbooks_service.create_expense = AsyncMock(
            side_effect=Exception("QuickBooks API error")
        )

        with pytest.raises(APIError, match="Failed to process receipt"):
            await mock_cli.process_receipt(test_file, dry_run=False)
