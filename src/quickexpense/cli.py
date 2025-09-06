"""QuickExpense CLI interface - simplified version."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from quickexpense.core.config import get_settings
from quickexpense.models import Expense, ReceiptExtractionRequest
from quickexpense.services.gemini import GeminiService
from quickexpense.services.quickbooks import QuickBooksClient, QuickBooksService
from quickexpense.services.token_store import TokenStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Supported image formats
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


class CLIError(Exception):
    """Base exception for CLI errors."""


class FileValidationError(CLIError):
    """File validation error."""


class APIError(CLIError):
    """API communication error."""


class QuickExpenseCLI:
    """Main CLI application class."""

    def __init__(self) -> None:
        """Initialize the CLI application."""
        self.settings = get_settings()
        self.gemini_service: GeminiService | None = None
        self.quickbooks_service: QuickBooksService | None = None
        self.quickbooks_client: QuickBooksClient | None = None

    async def initialize_services(self) -> None:
        """Initialize API services with proper authentication."""
        try:
            # Initialize token store and load tokens
            token_store = TokenStore()
            token_data = token_store.load_tokens()

            if not token_data:
                msg = (
                    "No authentication tokens found. Please run OAuth setup first:\n"
                    "  python scripts/connect_quickbooks_cli.py"
                )
                raise APIError(msg)

            # Initialize Gemini service
            self.gemini_service = GeminiService(self.settings)

            # Get company ID from tokens
            company_id = token_data.get("company_id")
            if not company_id:
                raise APIError("No company_id found in tokens")

            # Initialize QuickBooks client with simple auth
            self.quickbooks_client = QuickBooksClient(
                base_url=str(self.settings.qb_base_url),
                company_id=company_id,
                access_token=token_data.get("access_token"),
            )

            # Initialize QuickBooks service
            self.quickbooks_service = QuickBooksService(client=self.quickbooks_client)

            logger.info("Services initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize services")
            raise APIError(f"Failed to initialize services: {e}") from e

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.quickbooks_client:
            await self.quickbooks_client.close()

    def validate_file(self, file_path: Path) -> None:
        """Validate that the file exists and is a supported format."""
        if not file_path.exists():
            raise FileValidationError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise FileValidationError(f"Not a file: {file_path}")

        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            msg = (
                f"Unsupported file format: {file_path.suffix}\n"
                f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )
            raise FileValidationError(msg)

    async def process_receipt(
        self,
        file_path: Path,
        dry_run: bool = False,  # noqa: FBT001, FBT002
    ) -> dict[str, Any]:
        """Process a single receipt file."""
        logger.info("Processing receipt: %s", file_path)

        try:
            # Read and encode image
            image_data = file_path.read_bytes()
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Extract receipt data
            print(f"\nExtracting data from receipt: {file_path.name}")  # noqa: T201
            receipt_request = ReceiptExtractionRequest(
                image_base64=image_base64,
                category="General",  # Default category
                additional_context=None,
            )

            # Use Gemini service directly
            if not self.gemini_service:
                raise APIError("Gemini service not initialized")

            receipt_data = await self.gemini_service.extract_receipt_data(
                receipt_request.image_base64,
                receipt_request.additional_context,
            )

            # Convert to expense
            expense_dict = receipt_data.to_expense(receipt_request.category)

            result: dict[str, Any] = {
                "receipt": receipt_data.model_dump(),
                "expense": expense_dict,
                "file": str(file_path),
            }

            if dry_run:
                result["dry_run"] = True
                result["message"] = "DRY RUN - No expense created in QuickBooks"
            else:
                # Create expense in QuickBooks
                if not self.quickbooks_service:
                    raise APIError("QuickBooks service not initialized")

                print("\nCreating expense in QuickBooks...")  # noqa: T201
                expense = Expense(**expense_dict)
                qb_response = await self.quickbooks_service.create_expense(expense)
                result["quickbooks_response"] = qb_response
                msg = (
                    f"Successfully created expense in QuickBooks "
                    f"(ID: {qb_response.get('Id', 'Unknown')})"
                )
                result["message"] = msg

            return result

        except ValidationError as e:
            logger.error("Validation error: %s", e)
            raise APIError(f"Invalid data format: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %s", e)
            raise APIError(f"API request failed: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error processing receipt")
            raise APIError(f"Failed to process receipt: {e}") from e

    def format_output(self, result: dict[str, Any], output_format: str) -> str:
        """Format the output based on the requested format."""
        if output_format == "json":
            return json.dumps(result, indent=2, default=str)

        # Human-readable format
        receipt = result.get("receipt", {})
        expense = result.get("expense", {})
        lines = []

        if result.get("dry_run"):
            lines.append("\n=== DRY RUN MODE ===")

        lines.extend(
            [
                "\n=== Receipt Data ===",
                f"File: {result.get('file', 'Unknown')}",
                f"Vendor: {receipt.get('vendor_name', 'Unknown')}",
                f"Date: {receipt.get('transaction_date', 'Unknown')}",
                f"Total Amount: ${receipt.get('total_amount', '0.00')}",
                f"Tax: ${receipt.get('tax_amount', '0.00')}",
                f"Currency: {receipt.get('currency', 'USD')}",
            ]
        )

        if receipt.get("line_items"):
            lines.append("\nItems:")
            lines.extend(
                (
                    f"  - {item.get('description', 'Unknown')} "
                    f"(${item.get('total_price', '0.00')})"
                )
                for item in receipt["line_items"]
            )

        lines.extend(
            [
                "\n=== Expense Data ===",
                f"Category: {expense.get('category', 'General')}",
                f"Description: {expense.get('description', 'N/A')}",
                f"Payment Account: {expense.get('payment_account', 'Unknown')}",
            ]
        )

        if result.get("message"):
            lines.extend(["\n=== Result ===", result["message"]])

        return "\n".join(lines)

    async def upload_command(self, args: argparse.Namespace) -> None:
        """Handle the upload command."""
        file_path = Path(args.receipt)

        try:
            # Validate file
            self.validate_file(file_path)

            # Initialize services
            await self.initialize_services()

            # Process receipt
            result = await self.process_receipt(file_path, dry_run=args.dry_run)

            # Format and display output
            output = self.format_output(result, args.output)
            print(output)  # noqa: T201

            if not args.dry_run and "quickbooks_response" in result:
                sys.exit(0)  # Success
            elif args.dry_run:
                sys.exit(0)  # Success in dry-run mode
            else:
                sys.exit(1)  # Failed to create expense

        except FileValidationError as e:
            print(f"\nError: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(2)
        except APIError as e:
            print(f"\nError: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(3)
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user", file=sys.stderr)  # noqa: T201
            sys.exit(130)
        except Exception as e:
            logger.exception("Unexpected error")
            print(f"\nUnexpected error: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(1)
        finally:
            await self.cleanup()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="QuickExpense CLI - Process receipts into QuickBooks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  quickexpense upload receipt.jpeg
  quickexpense upload receipt.png --dry-run
  quickexpense upload receipt.jpg --output json

Supported formats: JPEG, PNG, GIF, BMP, WebP
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=True,
    )

    # Upload command
    upload_parser = subparsers.add_parser(
        "upload",
        help="Upload a single receipt",
        description=(
            "Process a single receipt image and create an expense in QuickBooks"
        ),
    )
    upload_parser.add_argument(
        "receipt",
        type=str,
        help="Path to the receipt image file",
    )
    upload_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview extracted data without creating expense in QuickBooks",
    )
    upload_parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    return parser


async def async_main() -> None:
    """Async main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    cli = QuickExpenseCLI()

    if args.command == "upload":
        await cli.upload_command(args)
    else:
        parser.error(f"Unknown command: {args.command}")


def main() -> None:
    """Main entry point for the CLI."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user", file=sys.stderr)  # noqa: T201
        sys.exit(130)
    except Exception as e:
        logger.exception("Fatal error in main")
        print(f"\nFatal error: {e}", file=sys.stderr)  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
