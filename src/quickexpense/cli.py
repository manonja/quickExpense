"""QuickExpense CLI interface - simplified version."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from quickexpense.core.config import get_settings
from quickexpense.models import Expense, ReceiptExtractionRequest
from quickexpense.models.business_rules import ExpenseContext
from quickexpense.models.enhanced_expense import (
    CategorizedLineItem,
    MultiCategoryExpense,
)
from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenResponse,
)
from quickexpense.services.business_rules import BusinessRuleEngine
from quickexpense.services.gemini import GeminiService
from quickexpense.services.quickbooks import (
    QuickBooksClient,
    QuickBooksError,
    QuickBooksService,
)
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from quickexpense.services.token_store import TokenStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Supported file formats (images and PDFs)
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".pdf"}


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
        self.oauth_manager: QuickBooksOAuthManager | None = None
        self.business_rules_engine: BusinessRuleEngine | None = None

    def _load_and_validate_tokens(self) -> tuple[dict[str, Any], str]:
        """Load and validate authentication tokens."""
        token_store = TokenStore()
        token_data = token_store.load_tokens()

        if not token_data:
            msg = (
                "No authentication tokens found. Please authenticate first:\n"
                "  quickexpense auth"
            )
            raise APIError(msg)

        company_id = token_data.get("company_id")
        if not company_id:
            raise APIError("No company_id found in tokens")

        return token_data, company_id

    def _create_oauth_manager(
        self, token_data: dict[str, Any], company_id: str
    ) -> QuickBooksOAuthManager | None:
        """Create OAuth manager with token validation."""
        oauth_config = QuickBooksOAuthConfig(
            client_id=self.settings.qb_client_id,
            client_secret=self.settings.qb_client_secret,
            redirect_uri=self.settings.qb_redirect_uri,
            token_refresh_buffer=self.settings.qb_token_refresh_buffer,
            max_refresh_attempts=self.settings.qb_max_refresh_attempts,
        )

        try:
            token_response = QuickBooksTokenResponse(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data.get("expires_in", 3600),
                x_refresh_token_expires_in=token_data.get(
                    "x_refresh_token_expires_in", 8640000
                ),
                token_type=token_data.get("token_type", "bearer"),
            )

            token_info = token_response.to_token_info()
            self._validate_token_expiry(token_info)

            oauth_manager = QuickBooksOAuthManager(
                oauth_config, initial_tokens=token_info
            )
            self._setup_token_callback(oauth_manager, company_id)
            return oauth_manager

        except (ValueError, TypeError, KeyError) as e:
            logger.error("Failed to initialize OAuth manager: %s", e)
            return None

    def _validate_token_expiry(self, token_info: Any) -> None:  # noqa: ANN401
        """Validate token expiry status."""
        if token_info.access_token_expired and token_info.refresh_token_expired:
            msg = (
                "OAuth tokens have completely expired. "
                "Please re-authenticate:\n  quickexpense auth --force"
            )
            raise APIError(msg)
        if token_info.refresh_token_expired:
            msg = (
                "Refresh token has expired. "
                "Please re-authenticate:\n  quickexpense auth --force"
            )
            raise APIError(msg)
        if token_info.access_token_expired:
            logger.info("Access token expired, will attempt refresh during API calls")

    def _setup_token_callback(
        self, oauth_manager: QuickBooksOAuthManager, company_id: str
    ) -> None:
        """Set up token save callback for OAuth manager."""
        token_store = TokenStore()

        def save_tokens_callback(tokens: Any) -> None:  # noqa: ANN401
            """Save updated tokens back to file."""
            updated_data = {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_in": 3600,  # Default 1 hour
                "x_refresh_token_expires_in": 8640000,  # Default 100 days
                "token_type": "bearer",
                "company_id": company_id,
            }
            token_store.save_tokens(updated_data)

        oauth_manager.add_token_update_callback(save_tokens_callback)

    async def initialize_services(self) -> None:
        """Initialize API services with proper authentication."""
        try:
            # Load and validate tokens
            token_data, company_id = self._load_and_validate_tokens()

            # Initialize Gemini service
            self.gemini_service = GeminiService(self.settings)

            # Create OAuth manager
            self.oauth_manager = self._create_oauth_manager(token_data, company_id)

            # Initialize QuickBooks client
            if self.oauth_manager:
                self.quickbooks_client = QuickBooksClient(
                    base_url=str(self.settings.qb_base_url),
                    company_id=company_id,
                    oauth_manager=self.oauth_manager,
                )
            else:
                # Fallback to direct token usage
                self.quickbooks_client = QuickBooksClient(
                    base_url=str(self.settings.qb_base_url),
                    company_id=company_id,
                    access_token=token_data.get("access_token"),
                )

            # Initialize QuickBooks service
            self.quickbooks_service = QuickBooksService(client=self.quickbooks_client)

            # Initialize Business Rules Engine
            config_path = (
                Path(__file__).parent.parent.parent / "config" / "business_rules.json"
            )
            self.business_rules_engine = BusinessRuleEngine(config_path)

            logger.info("Services initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize services")
            if "No authentication tokens found" in str(e):
                # Re-raise token errors with helpful message
                raise
            if "company_id" in str(e):
                msg = (
                    f"Invalid tokens: {e}\n"
                    "Please run OAuth setup again:\n  quickexpense auth --force"
                )
                raise APIError(msg) from e
            raise APIError(f"Failed to initialize services: {e}") from e

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.quickbooks_client:
            await self.quickbooks_client.close()
        # Note: OAuth manager cleanup is handled automatically when
        # it goes out of scope or by its internal HTTP client management

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

    def _create_categorized_items(
        self,
        receipt_data: Any,  # noqa: ANN401
        rule_results: list[Any],
    ) -> list[CategorizedLineItem]:
        """Create categorized line items from receipt and rule results."""
        categorized_items = []
        for line_item, rule_result in zip(
            receipt_data.line_items, rule_results, strict=False
        ):
            categorized_item = CategorizedLineItem(
                description=line_item.description,
                amount=line_item.total_price,  # Use total_price for receipt
                quantity=int(line_item.quantity),  # Convert Decimal to int
                category=rule_result.category,
                deductibility_percentage=rule_result.deductibility_percentage,
                account_mapping=rule_result.qb_account,
                tax_treatment=rule_result.tax_treatment.value,
                confidence_score=rule_result.confidence_score,
                business_rule_id=rule_result.business_rule_id,
            )
            categorized_items.append(categorized_item)
        return categorized_items

    def _create_enhanced_expense(
        self,
        receipt_data: Any,  # noqa: ANN401
        categorized_items: list[CategorizedLineItem],
        rule_results: list[Any],
    ) -> MultiCategoryExpense:
        """Create enhanced multi-category expense."""
        return MultiCategoryExpense(
            vendor_name=receipt_data.vendor_name,
            date=receipt_data.transaction_date,
            total_amount=receipt_data.total_amount,
            currency=receipt_data.currency,
            categorized_line_items=categorized_items,
            business_rules_applied=[
                rule_result.business_rule_id or "fallback"
                for rule_result in rule_results
            ],
            payment_method=receipt_data.payment_method.value,
            payment_account="Chequing",  # Default payment account
            total_deductible_amount=None,  # Will be auto-calculated
            foreign_exchange_rate=None,  # No FX for now
        )

    async def _extract_receipt_data(self, file_path: Path) -> Any:  # noqa: ANN401
        """Extract receipt data using Gemini AI."""
        # Read and encode image
        image_data = file_path.read_bytes()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # Extract receipt data using Gemini AI
        print(f"\nExtracting data from receipt: {file_path.name}")  # noqa: T201
        receipt_request = ReceiptExtractionRequest(
            image_base64=image_base64,
            category="General",  # Default category
            additional_context=None,
        )

        # Use Gemini service directly
        if not self.gemini_service:
            raise APIError("Gemini service not initialized")

        return await self.gemini_service.extract_receipt_data(
            receipt_request.image_base64,
            receipt_request.additional_context,
        )

    def _apply_business_rules(
        self,
        receipt_data: Any,  # noqa: ANN401
    ) -> tuple[list[Any], list[CategorizedLineItem], MultiCategoryExpense]:
        """Apply business rules to categorize line items."""
        print("Applying business rules for categorization...")  # noqa: T201
        if not self.business_rules_engine:
            raise APIError("Business rules engine not initialized")

        # Create expense context
        expense_context = ExpenseContext(
            vendor_name=receipt_data.vendor_name,
            vendor_address=receipt_data.vendor_address,
            postal_code=getattr(receipt_data, "postal_code", None),
            transaction_date=datetime.combine(
                receipt_data.transaction_date, datetime.min.time()
            ),
            total_amount=receipt_data.total_amount,
            currency=receipt_data.currency,
            payment_method=receipt_data.payment_method.value,
            business_purpose="Business expense",
            location=receipt_data.vendor_address,
        )

        # Categorize line items using business rules
        rule_results = self.business_rules_engine.categorize_line_items(
            receipt_data.line_items, expense_context
        )

        # Create categorized line items and enhanced expense
        categorized_items = self._create_categorized_items(receipt_data, rule_results)
        enhanced_expense = self._create_enhanced_expense(
            receipt_data, categorized_items, rule_results
        )

        return rule_results, categorized_items, enhanced_expense

    def _create_result_structure(
        self,
        file_path: Path,
        receipt_data: Any,  # noqa: ANN401
        enhanced_expense: MultiCategoryExpense,
        rule_results: list[Any],
    ) -> dict[str, Any]:
        """Create the result structure for the processed receipt."""
        return {
            "receipt": receipt_data.model_dump(),
            "enhanced_expense": enhanced_expense.model_dump(),
            "business_rules": {
                "rule_applications": [
                    {
                        "line_item": line_item.description,
                        "rule_applied": (
                            rule_result.rule_applied.name
                            if rule_result.rule_applied
                            else "Fallback Rule"
                        ),
                        "category": rule_result.category,
                        "deductibility_percentage": (
                            rule_result.deductibility_percentage
                        ),
                        "qb_account": rule_result.qb_account,
                        "tax_treatment": rule_result.tax_treatment.value,
                        "confidence_score": rule_result.confidence_score,
                        "is_fallback": rule_result.is_fallback,
                    }
                    for line_item, rule_result in zip(
                        receipt_data.line_items, rule_results, strict=False
                    )
                ],
                "total_deductible_amount": float(
                    enhanced_expense.total_deductible_amount or 0
                ),
                "deductible_by_category": {
                    category: float(amount)
                    for category, amount in (
                        enhanced_expense.get_deductible_amount_by_category().items()
                    )
                },
            },
            "file": str(file_path),
        }

    async def _create_quickbooks_expense(
        self,
        enhanced_expense: MultiCategoryExpense,
        categorized_items: list[CategorizedLineItem],
    ) -> dict[str, Any]:
        """Create expense in QuickBooks from enhanced expense data."""
        # TODO(manonja): Implement multi-category expense support  # noqa: FIX002
        # https://github.com/project/quickExpense/issues/XXX
        # Need to update QB service to handle multi-category expenses
        print("\nCreating expense in QuickBooks...")  # noqa: T201
        if not self.quickbooks_service:
            raise APIError("QuickBooks service not initialized")

        # Use the first categorized item for primary category
        primary_item = categorized_items[0] if categorized_items else None

        expense = Expense(
            vendor_name=enhanced_expense.vendor_name,
            amount=enhanced_expense.total_amount,
            date=enhanced_expense.date,
            currency=enhanced_expense.currency,
            category=(
                primary_item.category if primary_item else "General Business Expense"
            ),
        )
        qb_response = await self.quickbooks_service.create_expense(expense)
        purchase_id = qb_response.get("Purchase", {}).get("Id", "Unknown")
        return {
            "quickbooks_response": qb_response,
            "message": (
                f"Successfully created expense in QuickBooks (ID: {purchase_id})"
            ),
        }

    async def process_receipt(
        self,
        file_path: Path,
        dry_run: bool = False,  # noqa: FBT001, FBT002
    ) -> dict[str, Any]:
        """Process a single receipt file with business rules categorization."""
        logger.info("Processing receipt: %s", file_path)

        try:
            # Extract receipt data
            receipt_data = await self._extract_receipt_data(file_path)

            # Apply business rules
            rule_results, categorized_items, enhanced_expense = (
                self._apply_business_rules(receipt_data)
            )

            # Create result structure
            result = self._create_result_structure(
                file_path, receipt_data, enhanced_expense, rule_results
            )

            if dry_run:
                result["dry_run"] = True
                result["message"] = "DRY RUN - No expense created in QuickBooks"
            else:
                # Create expense in QuickBooks
                qb_result = await self._create_quickbooks_expense(
                    enhanced_expense, categorized_items
                )
                result.update(qb_result)

            return result

        except ValidationError as e:
            logger.error("Validation error: %s", e)
            raise APIError(f"Invalid data format: {e}") from e
        except QuickBooksError as e:
            logger.error("QuickBooks error: %s", e)
            # Check for specific authentication errors
            if (
                "401 Unauthorized" in str(e)
                or "Token expired" in str(e)
                or "AuthenticationFailed" in str(e)
            ):
                msg = (
                    "QuickBooks authentication has expired. "
                    "Please re-authenticate:\n  quickexpense auth --force"
                )
                raise APIError(msg) from e
            raise APIError(f"QuickBooks API error: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %s", e)
            # Check for specific authentication errors
            http_unauthorized = 401
            if e.response.status_code == http_unauthorized:
                response_text = str(e.response.text)
                if (
                    "Token expired" in response_text
                    or "AuthenticationFailed" in response_text
                ):
                    msg = (
                        "QuickBooks authentication has expired. "
                        "Please re-authenticate:\n  quickexpense auth --force"
                    )
                    raise APIError(msg) from e
            raise APIError(f"API request failed: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error processing receipt")
            raise APIError(f"Failed to process receipt: {e}") from e

    def format_output(self, result: dict[str, Any], output_format: str) -> str:
        """Format the output based on the requested format."""
        if output_format == "json":
            return json.dumps(result, indent=2, default=str)

        # Human-readable format with business rules information
        receipt = result.get("receipt", {})
        enhanced_expense = result.get("enhanced_expense", {})
        business_rules = result.get("business_rules", {})
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
                f"Currency: {receipt.get('currency', 'CAD')}",
            ]
        )

        # Show line items with business rules categorization
        rule_applications = business_rules.get("rule_applications", [])
        if rule_applications:
            lines.append("\n=== Business Rules Categorization ===")
            for app in rule_applications:
                lines.extend(
                    [
                        f"\n📄 {app.get('line_item', 'Unknown Item')}",
                        f"   Rule Applied: {app.get('rule_applied', 'Unknown')}",
                        f"   Category: {app.get('category', 'Unknown')}",
                        f"   QuickBooks Account: {app.get('qb_account', 'Unknown')}",
                        f"   Tax Deductible: {app.get('deductibility_percentage', 0)}%",
                        f"   Tax Treatment: {app.get('tax_treatment', 'standard')}",
                        f"   Confidence: {app.get('confidence_score', 0):.1%}",
                        (
                            "   ⚠️  Fallback Rule Applied"
                            if app.get("is_fallback")
                            else "   ✅ Matched Rule"
                        ),
                    ]
                )

        # Show tax summary
        if business_rules:
            total_deductible = float(business_rules.get("total_deductible_amount", 0))
            total_amount = float(enhanced_expense.get("total_amount", 0))
            deductible_percentage = (
                (total_deductible / total_amount * 100) if total_amount > 0 else 0
            )

            lines.extend(
                [
                    "\n=== Tax Deductibility Summary ===",
                    f"Total Amount: ${total_amount:.2f}",
                    (
                        f"Deductible Amount: ${total_deductible:.2f} "
                        f"({deductible_percentage:.1f}%)"
                    ),
                ]
            )

            # Show breakdown by category
            deductible_by_category = business_rules.get("deductible_by_category", {})
            if deductible_by_category:
                lines.append("\nDeductible by Category:")
                for category, amount in deductible_by_category.items():
                    lines.append(f"  • {category}: ${amount:.2f}")

        # Show enhanced expense summary
        if enhanced_expense:
            # Calculate unique categories
            categorized_items = enhanced_expense.get("categorized_line_items", [])
            unique_categories = len(
                {item.get("category", "") for item in categorized_items}
            )

            lines.extend(
                [
                    "\n=== Enhanced Expense Summary ===",
                    f"Vendor: {enhanced_expense.get('vendor_name', 'Unknown')}",
                    (
                        f"Categories: {len(categorized_items)} items across "
                        f"{unique_categories} categories"
                    ),
                    (
                        "Business Rules Applied: "
                        f"{len(enhanced_expense.get('business_rules_applied', []))}"
                    ),
                    f"Payment: {enhanced_expense.get('payment_method', 'unknown')}",
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

    async def auth_command(self, args: argparse.Namespace) -> None:
        """Handle the authentication command."""
        try:
            # Check if tokens already exist
            token_store = TokenStore()
            existing_tokens = token_store.load_tokens()

            if existing_tokens and not args.force:
                print("✅ Authentication tokens already exist!")  # noqa: T201
                print("   Use --force to re-authenticate")  # noqa: T201
                print(  # noqa: T201
                    f"   Company ID: {existing_tokens.get('company_id', 'Unknown')}"
                )
                return

            print("🚀 Starting QuickBooks authentication...")  # noqa: T201
            print("   This will open your browser for OAuth setup.")  # noqa: T201

            # Import and run the OAuth script functionality
            import subprocess

            result = subprocess.run(  # noqa: ASYNC221, S603
                [  # noqa: S607
                    "uv",
                    "run",
                    "python",
                    "scripts/connect_quickbooks_cli.py",
                ],
                capture_output=False,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                print("\n✅ Authentication successful!")  # noqa: T201
                print(  # noqa: T201
                    "   You can now upload receipts with: quickexpense upload <receipt>"
                )
            else:
                print("\n❌ Authentication failed!")  # noqa: T201
                sys.exit(1)

        except KeyboardInterrupt:
            print("\n\n⚠️  Authentication cancelled by user")  # noqa: T201
            sys.exit(130)
        except Exception as e:  # noqa: BLE001
            print(f"\n❌ Authentication error: {e}")  # noqa: T201
            sys.exit(1)

    def _check_authentication_status(self) -> dict[str, Any] | None:
        """Check authentication token status."""
        token_store = TokenStore()
        token_data = token_store.load_tokens()

        if not token_data:
            print("❌ Authentication: Not authenticated")  # noqa: T201
            print("   Run: quickexpense auth")  # noqa: T201
            return None

        print("✅ Authentication: Tokens found")  # noqa: T201
        print(f"   Company ID: {token_data.get('company_id', 'Unknown')}")  # noqa: T201
        return token_data

    def _validate_token_status(self, token_data: dict[str, Any]) -> None:
        """Validate token expiry status."""
        try:
            token_response = QuickBooksTokenResponse(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data.get("expires_in", 3600),
                x_refresh_token_expires_in=token_data.get(
                    "x_refresh_token_expires_in", 8640000
                ),
                token_type=token_data.get("token_type", "bearer"),
            )
            token_info = token_response.to_token_info()

            if token_info.refresh_token_expired:
                print("❌ Token Status: Refresh token expired")  # noqa: T201
                print("   Run: quickexpense auth --force")  # noqa: T201
            elif token_info.access_token_expired:
                print(  # noqa: T201
                    "⚠️  Token Status: Access token expired (will auto-refresh)"
                )
            else:
                print("✅ Token Status: Valid")  # noqa: T201

        except Exception as e:  # noqa: BLE001
            print(f"⚠️  Token Status: Cannot validate ({e})")  # noqa: T201

    async def _test_quickbooks_connection(self) -> None:
        """Test QuickBooks API connection."""
        print("\n🔌 Testing QuickBooks connection...")  # noqa: T201
        try:
            await self.initialize_services()
            if self.quickbooks_service:
                # Try a simple API call
                accounts = await self.quickbooks_service.get_expense_accounts()
                print(  # noqa: T201
                    f"✅ QuickBooks API: Connected ({len(accounts)} expense accounts)"
                )
            else:
                print("❌ QuickBooks API: Service not initialized")  # noqa: T201
        except Exception as e:  # noqa: BLE001
            print(f"❌ QuickBooks API: Connection failed ({e})")  # noqa: T201
            print("   Try: quickexpense auth --force")  # noqa: T201

    def _check_gemini_status(self) -> None:
        """Check Gemini AI configuration status."""
        print("\n🤖 Testing Gemini AI...")  # noqa: T201
        try:
            if self.settings.gemini_api_key:
                print("✅ Gemini AI: API key configured")  # noqa: T201
            else:
                print("❌ Gemini AI: No API key found")  # noqa: T201
                print("   Set GEMINI_API_KEY environment variable")  # noqa: T201
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  Gemini AI: Error checking configuration ({e})")  # noqa: T201

    def _check_business_rules_status(self) -> None:
        """Check Business Rules Engine status."""
        print("\n📋 Testing Business Rules Engine...")  # noqa: T201
        try:
            if self.business_rules_engine:
                rule_count = (
                    len(self.business_rules_engine.config.rules)
                    if self.business_rules_engine.config
                    else 0
                )
                print(f"✅ Business Rules: Loaded ({rule_count} rules)")  # noqa: T201

                # Validate configuration
                errors = self.business_rules_engine.validate_configuration()
                if errors:
                    print(f"⚠️  Configuration warnings: {len(errors)}")  # noqa: T201
                    for error in errors[:3]:  # Show first 3 errors
                        print(f"   - {error}")  # noqa: T201
                else:
                    print("✅ Configuration: Valid")  # noqa: T201
            else:
                print("❌ Business Rules: Engine not initialized")  # noqa: T201
        except Exception as e:  # noqa: BLE001
            print(f"❌ Business Rules: Configuration error ({e})")  # noqa: T201

    async def status_command(self, args: argparse.Namespace) -> None:  # noqa: ARG002
        """Handle the status command."""
        try:
            print("🔍 QuickExpense System Status")  # noqa: T201
            print("=" * 40)  # noqa: T201

            # Check authentication
            token_data = self._check_authentication_status()
            if not token_data:
                return

            # Validate token status
            self._validate_token_status(token_data)

            # Test connections and services
            await self._test_quickbooks_connection()
            self._check_gemini_status()
            self._check_business_rules_status()

        except Exception as e:  # noqa: BLE001
            print(f"\n❌ Status check error: {e}")  # noqa: T201
            sys.exit(1)
        finally:
            await self.cleanup()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="QuickExpense CLI - Process receipts with AI and business rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  quickexpense upload receipt.jpeg
  quickexpense upload marriott.pdf --dry-run
  quickexpense upload receipt.png --output json

Features:
  • AI-powered receipt extraction (Gemini)
  • Business rules for automatic categorization
  • Canadian tax compliance (CRA Section 67.1)
  • Multi-category expense support
  • PDF and image processing

Supported formats: JPEG, PNG, GIF, BMP, WebP, PDF
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

    # Auth command
    auth_parser = subparsers.add_parser(
        "auth",
        help="Authenticate with QuickBooks",
        description="Set up OAuth authentication with QuickBooks",
    )
    auth_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-authentication even if tokens exist",
    )

    # Status command
    subparsers.add_parser(
        "status",
        help="Check system status",
        description="Check authentication and system status",
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
    elif args.command == "auth":
        await cli.auth_command(args)
    elif args.command == "status":
        await cli.status_command(args)
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
