"""QuickExpense CLI interface - simplified version."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from quickexpense import __version__
from quickexpense.core.config import get_settings
from quickexpense.core.logging_config import LoggingConfig
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
from quickexpense.services.audit_logger import AuditLogger
from quickexpense.services.business_rules import BusinessRuleEngine
from quickexpense.services.gemini import GeminiService
from quickexpense.services.quickbooks import (
    QuickBooksClient,
    QuickBooksError,
    QuickBooksService,
)
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from quickexpense.services.token_store import TokenStore

# Constants
MAX_DISPLAY_ITEMS = 3

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

        # Initialize audit logging
        self.audit_config = LoggingConfig()
        self.audit_logger = AuditLogger(self.audit_config)
        self.current_correlation_id: str | None = None

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

        except APIError:
            # Re-raise CLI errors
            raise
        except Exception as e:
            logger.error("Failed to initialize services: %s", e)
            raise APIError(f"Service initialization failed: {e}") from e

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.quickbooks_client:
            await self.quickbooks_client.close()

    def validate_file(self, file_path: Path) -> None:
        """Validate the input file."""
        # Check if file exists
        if not file_path.exists():
            raise FileValidationError(f"File not found: {file_path}")

        # Check if it's a file (not a directory)
        if not file_path.is_file():
            raise FileValidationError(f"Not a file: {file_path}")

        # Check file extension
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            supported = ", ".join(sorted(SUPPORTED_FORMATS))
            raise FileValidationError(
                f"Unsupported file format '{suffix}'. Supported: {supported}"
            )

        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        file_size = file_path.stat().st_size
        if file_size > max_size:
            size_mb = file_size / (1024 * 1024)
            raise FileValidationError(f"File too large ({size_mb:.1f}MB). Max: 10MB")

        # Check read permissions
        if not file_path.is_file() or not file_path.exists():
            raise FileValidationError(f"Cannot read file: {file_path}")

    async def _extract_receipt_data(
        self, file_path: Path
    ) -> Any:  # Support both ExtractedReceipt and dict  # noqa: ANN401
        """Extract receipt data using Gemini AI."""
        print(f"\nExtracting data from receipt: {file_path.name}")  # noqa: T201

        if not self.gemini_service:
            raise APIError("Gemini service not initialized")

        # Read file content
        with file_path.open("rb") as f:
            image_data = f.read()

        # Create extraction request
        request = ReceiptExtractionRequest(
            image_base64=base64.b64encode(image_data).decode("utf-8"),
            category="General",
            additional_context="",
        )

        # Extract data
        return await self.gemini_service.extract_receipt_data(request.image_base64)

    async def _extract_receipt_data_with_debug(self, file_path: Path) -> dict[str, Any]:
        """Extract receipt data with additional debug output."""
        print(f"\nExtracting data from receipt: {file_path.name}")  # noqa: T201

        # Show file info
        print(f"  File size: {file_path.stat().st_size / 1024:.1f} KB")  # noqa: T201
        print(f"  File type: {file_path.suffix.lower()}")  # noqa: T201

        result = await self._extract_receipt_data(file_path)
        # Cast to dict for type checking - handles both dict and Pydantic models
        result_dict: dict[str, Any] = (
            result if isinstance(result, dict) else result.model_dump()
        )

        print("\nExtracted data:")  # noqa: T201
        print(f"  Vendor: {result_dict.get('vendor_name', 'Unknown')}")  # noqa: T201
        print(f"  Date: {result_dict.get('transaction_date', 'Unknown')}")  # noqa: T201
        print(f"  Amount: ${result_dict.get('total_amount', '0.00')}")  # noqa: T201
        print(f"  Tax: ${result_dict.get('tax_amount', '0.00')}")  # noqa: T201
        print(f"  Currency: {result_dict.get('currency', 'CAD')}")  # noqa: T201

        line_items = result_dict.get("line_items", [])
        if line_items:
            print(f"\n  Line items: {len(line_items)}")  # noqa: T201
            for idx, item in enumerate(line_items[:MAX_DISPLAY_ITEMS], 1):
                desc = item.get("description", "No description")[:50]
                amount = item.get("amount", "0.00")
                print(f"    {idx}. {desc} - ${amount}")  # noqa: T201
            if len(line_items) > MAX_DISPLAY_ITEMS:
                # fmt: off
                print(f"    ... and {len(line_items) - MAX_DISPLAY_ITEMS} more")  # noqa: T201
                # fmt: on

        return result_dict

    def _apply_business_rules(
        self,
        receipt_data: Any,  # Support both dict and Pydantic models  # noqa: ANN401
    ) -> tuple[list[dict[str, Any]], list[CategorizedLineItem], MultiCategoryExpense]:
        """Apply business rules with enhanced categorization."""
        print("\nApplying business rules for categorization...")  # noqa: T201

        if not self.business_rules_engine:
            raise APIError("Business rules engine not initialized")

        # Handle both dict and Pydantic model formats for backward compatibility
        if hasattr(receipt_data, "vendor_name"):
            # Pydantic model (ExtractedReceipt)
            vendor_name = receipt_data.vendor_name
            total_amount = receipt_data.total_amount
            transaction_date = receipt_data.transaction_date
            currency = receipt_data.currency
            line_items = receipt_data.line_items
        else:
            # Dictionary format
            vendor_name = receipt_data.get("vendor_name", "")
            total_amount = Decimal(str(receipt_data.get("total_amount", 0)))
            transaction_date = receipt_data.get("date", "")
            currency = receipt_data.get("currency", "CAD")
            line_items = receipt_data.get("line_items", [])

        # Create expense context for business rules
        context = ExpenseContext(
            vendor_name=vendor_name,
            total_amount=total_amount,
            transaction_date=transaction_date,
            currency=currency,
            vendor_address=None,
            postal_code=None,
            payment_method=None,
            business_purpose=None,
            location=None,
        )

        # Use existing categorize_line_items method
        rule_results = self.business_rules_engine.categorize_line_items(
            line_items, context
        )

        # Convert rule results to the expected format for both audit logging and display
        rule_applications = []
        for i, result in enumerate(rule_results):
            # Get original line item data for description
            original_item = line_items[i] if i < len(line_items) else {}

            # Handle line item description - support both Pydantic models and dicts
            if hasattr(original_item, "description"):
                line_item_desc = getattr(original_item, "description", "Unknown Item")
            elif isinstance(original_item, dict):
                line_item_desc = original_item.get("description", "Unknown Item")
            else:
                line_item_desc = "Unknown Item"

            rule_applications.append(
                {
                    "id": result.business_rule_id or "unknown",
                    "name": (
                        result.rule_applied.name
                        if result.rule_applied
                        else "Unknown Rule"
                    ),
                    # Add fields for display formatter
                    "line_item": line_item_desc,
                    "rule_applied": (
                        result.rule_applied.name if result.rule_applied else "Unknown"
                    ),
                    "confidence": result.confidence_score,
                    "confidence_score": result.confidence_score,  # Both formats
                    "items_affected": 1,
                    "category": result.category,
                    "qb_account": result.qb_account,
                    "t2125_line_item": None,  # TODO @dev: Add to RuleActions model  # noqa: FIX002, E501
                    # https://github.com/company/quickexpense/issues/PRE-118
                    "deductibility_percentage": result.deductibility_percentage,
                    "tax_treatment": result.tax_treatment,
                    "ita_reference": None,  # TODO @dev: Add to RuleActions model  # noqa: FIX002, E501
                    # https://github.com/company/quickexpense/issues/PRE-118
                    "is_fallback": result.is_fallback,
                }
            )

        # Convert to categorized line items
        categorized_items = []
        for i, result in enumerate(rule_results):
            # Get original line item data
            original_item = line_items[i] if i < len(line_items) else {}

            # Handle line item data (could be LineItem model or dict)
            if hasattr(original_item, "description"):
                # LineItem model
                item_description = getattr(
                    original_item, "description", "Processed line item"
                )
                # Use total_price for LineItem models, fallback to unit_price
                item_amount = getattr(
                    original_item,
                    "total_price",
                    getattr(original_item, "unit_price", Decimal("0")),
                )
            elif isinstance(original_item, dict):
                # Dictionary format
                item_description = original_item.get(
                    "description", "Processed line item"
                )
                item_amount = Decimal(str(original_item.get("amount", 0)))
            else:
                item_description = "Processed line item"
                item_amount = Decimal("0")

            categorized_items.append(
                CategorizedLineItem(
                    description=item_description,
                    amount=item_amount,
                    category=result.category,
                    deductibility_percentage=result.deductibility_percentage,
                    account_mapping=result.account_mapping,
                    tax_treatment=result.tax_treatment,
                    confidence_score=result.confidence_score,
                    business_rule_id=result.business_rule_id,
                )
            )

        # Create enhanced expense using existing data
        enhanced_expense = MultiCategoryExpense(
            vendor_name=vendor_name,
            total_amount=total_amount,
            date=transaction_date,
            currency=currency,
            categorized_line_items=categorized_items,
            total_deductible_amount=None,  # Will be auto-calculated
            foreign_exchange_rate=None,
            payment_account=None,
        )

        return (rule_applications, categorized_items, enhanced_expense)

    def _create_result_structure(
        self,
        file_path: Path,
        receipt_data: dict[str, Any],
        enhanced_expense: MultiCategoryExpense,
        rule_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create structured result for output."""
        # Calculate deductibility summary
        total_deductible = sum(
            float(item.deductible_amount)
            for item in enhanced_expense.categorized_line_items
        )
        deductibility_rate = (
            total_deductible / float(enhanced_expense.total_amount) * 100
        )

        # Get unique categories
        categories = {item.category for item in enhanced_expense.categorized_line_items}

        # Build categorization summary
        categorization = {
            "total_items": len(enhanced_expense.categorized_line_items),
            "categories": list(categories),
            "business_rules_applied": len(rule_results),
            "confidence_scores": [r.get("confidence_score", 0) for r in rule_results],
            "tax_deductibility": {
                "total_amount": str(enhanced_expense.total_amount),
                "deductible_amount": f"{total_deductible:.2f}",
                "deductibility_rate": f"{deductibility_rate:.1f}%",
            },
        }

        # Add T2125 summary if sole proprietor
        if self.business_rules_engine and rule_results:
            # Convert rule_results to expected format for T2125 summary
            # For now, skip T2125 summary until we have proper mapping
            # TODO @dev: Implement proper T2125 mapping  # noqa: FIX002
            # https://github.com/company/quickexpense/issues/PRE-117
            pass

        return {
            "file": str(file_path),
            "receipt": receipt_data,
            "business_rules": {
                "rule_applications": rule_results,
                "categorization": categorization,
            },
            "enhanced_expense": enhanced_expense.model_dump(),
        }

    async def _create_quickbooks_expense(
        self,
        enhanced_expense: MultiCategoryExpense,
        categorized_items: list[CategorizedLineItem],
    ) -> dict[str, Any]:
        """Create expense in QuickBooks."""
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

    async def process_receipt(  # noqa: PLR0915, PLR0912, C901
        self,
        file_path: Path,
        dry_run: bool = False,  # noqa: FBT001, FBT002
        verbose: bool = False,  # noqa: FBT001, FBT002
    ) -> dict[str, Any]:
        """Process a single receipt file with business rules categorization."""
        logger.info("Processing receipt: %s", file_path)

        # Start audit trail
        start_time = time.time()
        user_context = {"entity_type": "sole_proprietorship", "verbose": verbose}
        correlation_id = self.audit_logger.start_expense_processing(
            str(file_path), user_context
        )
        self.current_correlation_id = correlation_id

        if verbose:
            print(f"\nCorrelation ID: {correlation_id}")  # noqa: T201
            audit_log_path = self.audit_logger.config.audit_log_path
            # fmt: off
            print(f"Audit trail: {audit_log_path / 'quickexpense_audit.log'}")  # noqa: T201
            # fmt: on

        try:
            # Extract receipt data with timing
            extract_start = time.time()
            receipt_data = await self._extract_receipt_data(file_path)
            extract_time = time.time() - extract_start

            # Log Gemini extraction
            # Handle both ExtractedReceipt model and dict for backward compatibility
            if hasattr(receipt_data, "confidence_score"):
                confidence_score = receipt_data.confidence_score
            else:
                confidence_score = receipt_data.get("confidence_score", 0.0)

            self.audit_logger.log_gemini_extraction(
                correlation_id,
                extract_time,
                confidence_score,
                receipt_data,
            )

            # Apply business rules with timing
            rule_results, categorized_items, enhanced_expense = (
                self._apply_business_rules(receipt_data)
            )

            # Log business rules application
            self._log_business_rules_application(
                correlation_id, rule_results, categorized_items, enhanced_expense
            )

            # Create result structure
            result = self._create_result_structure(
                file_path, receipt_data, enhanced_expense, rule_results
            )

            if dry_run:
                result["dry_run"] = True
                result["message"] = "DRY RUN - No expense created in QuickBooks"
                final_status = "dry_run_success"
            else:
                # Create expense in QuickBooks with timing
                qb_start = time.time()
                qb_result = await self._create_quickbooks_expense(
                    enhanced_expense, categorized_items
                )
                qb_time = time.time() - qb_start

                # Log QuickBooks integration
                self._log_quickbooks_integration(correlation_id, qb_result, qb_time)

                result.update(qb_result)
                final_status = "success"

            # Complete audit trail
            total_time = time.time() - start_time
            summary = self._create_processing_summary(enhanced_expense, rule_results)
            self.audit_logger.complete_expense_processing(
                correlation_id, total_time, final_status, summary
            )

            # Add audit info to result
            if verbose:
                result["audit_info"] = self.audit_logger.get_audit_summary(
                    correlation_id
                )

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

        # Handle both ExtractedReceipt model and dict for backward compatibility
        if hasattr(receipt, "vendor_name"):
            # ExtractedReceipt model
            vendor_name = receipt.vendor_name
            transaction_date = str(receipt.transaction_date)
            total_amount = str(receipt.total_amount)
            tax_amount = str(receipt.tax_amount)
            currency = receipt.currency
        else:
            # Dictionary format
            vendor_name = receipt.get("vendor_name", "Unknown")
            transaction_date = receipt.get("transaction_date", "Unknown")
            total_amount = str(receipt.get("total_amount", "0.00"))
            tax_amount = str(receipt.get("tax_amount", "0.00"))
            currency = receipt.get("currency", "CAD")

        lines.extend(
            [
                "\n=== Receipt Data ===",
                f"File: {result.get('file', 'Unknown')}",
                f"Vendor: {vendor_name}",
                f"Date: {transaction_date}",
                f"Total Amount: ${total_amount}",
                f"Tax: ${tax_amount}",
                f"Currency: {currency}",
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
                        f"   Tax Treatment: {str(app.get('tax_treatment', 'standard')).replace('TaxTreatment.', '').lower()}",  # noqa: E501
                        f"   Confidence: {app.get('confidence_score', 0):.1%}",
                        (
                            "   ⚠️  Fallback Rule Applied"
                            if app.get("is_fallback")
                            else "   ✅ Matched Rule"
                        ),
                    ]
                )

        # Show tax deductibility summary
        categorization = business_rules.get("categorization", {})
        if categorization.get("tax_deductibility"):
            tax_info = categorization["tax_deductibility"]
            deductible_amt = tax_info.get("deductible_amount", "0.00")
            rate = tax_info.get("deductibility_rate", "0%")
            lines.extend(
                [
                    "\n=== Tax Deductibility Summary ===",
                    f"Total Amount: ${tax_info.get('total_amount', '0.00')}",
                    f"Deductible Amount: ${deductible_amt} ({rate})",
                ]
            )

            # Show T2125 summary if available
            t2125 = categorization.get("t2125_summary", {})
            if t2125.get("line_items"):
                lines.append("\nDeductible by Category:")
                lines.extend(
                    [
                        f"  • {line_item['category']}: ${line_item['amount']:.2f}"
                        for line_item in t2125["line_items"]
                    ]
                )

        # Show enhanced expense summary
        if enhanced_expense:
            line_items = enhanced_expense.get("categorized_line_items", [])
            categories = categorization.get("categories", [])
            rules_applied = categorization.get("business_rules_applied", 0)
            payment = enhanced_expense.get("payment_account_ref", {}).get(
                "value", "cash"
            )
            lines.extend(
                [
                    "\n=== Enhanced Expense Summary ===",
                    f"Vendor: {enhanced_expense.get('vendor_name', 'Unknown')}",
                    f"Items: {len(line_items)}, Categories: {len(categories)}",
                    f"Business Rules Applied: {rules_applied}",
                    f"Payment: {payment}",
                ]
            )

        # Show result message
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
            result = await self.process_receipt(
                file_path, dry_run=args.dry_run, verbose=args.verbose
            )

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
            logger.exception("Unexpected error in upload command")
            print(f"\nUnexpected error: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(1)
        finally:
            await self.cleanup()

    async def auth_command(self, args: argparse.Namespace) -> None:  # noqa: ARG002
        """Handle the auth command."""
        try:
            # Run the OAuth connection script
            result = subprocess.run(  # noqa: S603, ASYNC221
                ["python", "scripts/connect_quickbooks_cli.py"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                print("✅ Authentication successful!")  # noqa: T201
                print("You can now use QuickExpense to process receipts.")  # noqa: T201
                sys.exit(0)
            else:
                # fmt: off
                print(f"❌ Authentication failed: {result.stderr}", file=sys.stderr)  # noqa: T201
                # fmt: on
                sys.exit(1)

        except FileNotFoundError:
            print(  # noqa: T201
                (
                    "\nError: OAuth connection script not found.\n"
                    "Please run from the project root directory."
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            logger.exception("Error during authentication")
            print(f"\nError during authentication: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(1)

    def _check_auth_status(self) -> None:
        """Check and display authentication status."""
        try:
            token_store = TokenStore()
            tokens = token_store.load_tokens()

            if tokens:
                print("✅ Authentication: Tokens found")  # noqa: T201
                # fmt: off
                print(f"   Company ID: {tokens.get('company_id', 'Unknown')}")  # noqa: T201
                # fmt: on

                # Check token validity
                try:
                    saved_at_str = tokens.get("saved_at")
                    if saved_at_str:
                        # Parse the saved_at timestamp
                        saved_at = datetime.fromisoformat(saved_at_str)
                        now = datetime.now(UTC)
                        age_hours = (now - saved_at).total_seconds() / 3600

                        # Access token expires in ~1 hour
                        if age_hours < 1:
                            print("✅ Token Status: Valid")  # noqa: T201
                        elif age_hours < 100 * 24:  # Refresh token ~100 days
                            # fmt: off
                            print("⚠️  Token Status: Expired (refresh available)")  # noqa: T201
                            # fmt: on
                        else:
                            print("❌ Token Status: Tokens expired")  # noqa: T201
                            print("   Run: quickexpense auth --force")  # noqa: T201
                    else:
                        print("⚠️  Token Status: Unknown (no timestamp)")  # noqa: T201
                except Exception:  # noqa: BLE001
                    print("⚠️  Token Status: Could not verify")  # noqa: T201
            else:
                print("❌ Authentication: No tokens found")  # noqa: T201
                print("   Run: quickexpense auth")  # noqa: T201
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  Authentication: Error checking status ({e})")  # noqa: T201

    async def _check_quickbooks_status(self) -> None:
        """Check QuickBooks API connectivity."""
        print("\n🔌 Testing QuickBooks connection...")  # noqa: T201
        try:
            await self.initialize_services()

            if self.quickbooks_service:
                # Test by fetching expense accounts
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
            self._check_auth_status()

            # Test connections
            await self._check_quickbooks_status()
            self._check_gemini_status()
            self._check_business_rules_status()

        except Exception as e:  # noqa: BLE001
            print(f"\n❌ Status check error: {e}")  # noqa: T201
            sys.exit(1)
        finally:
            await self.cleanup()

    def _log_business_rules_application(
        self,
        correlation_id: str,
        rule_results: list[dict[str, Any]],
        categorized_items: list[CategorizedLineItem],
        enhanced_expense: MultiCategoryExpense,  # noqa: ARG002
    ) -> None:
        """Log business rules application for audit trail."""
        # Convert rule results to audit format
        rules_applied = [
            {
                "id": result.get("id", "unknown"),
                "name": result.get("name", "Unknown Rule"),
                "confidence": result.get("confidence", 0.0),
                "items_affected": 1,
                "category": result.get("category", "Unknown"),
                "t2125_line_item": result.get("t2125_line_item"),
                "deductibility_percentage": result.get("deductibility_percentage", 100),
                "ita_reference": result.get("ita_reference"),
            }
            for result in rule_results
        ]

        # Convert categorized items to audit format
        items_data = [
            {
                "category": item.category,
                "amount": item.amount,
                "deductible_amount": item.deductible_amount,
                "t2125_line_item": getattr(item, "t2125_line_item", None),
                "compliance_note": getattr(item, "compliance_note", None),
            }
            for item in categorized_items
        ]

        self.audit_logger.log_business_rules_application(
            correlation_id, rules_applied, items_data, entity_type="sole_proprietorship"
        )

    def _log_quickbooks_integration(
        self,
        correlation_id: str,
        qb_result: dict[str, Any],
        processing_time: float,
    ) -> None:
        """Log QuickBooks integration for audit trail."""
        qb_response = qb_result.get("quickbooks_response", {})
        purchase = qb_response.get("Purchase", {})

        qb_entries = []
        if purchase:
            qb_entries.append(
                {
                    "id": purchase.get("Id", "unknown"),
                    "amount": float(purchase.get("TotalAmt", 0)),
                    "account": purchase.get("AccountRef", {}).get("name", "unknown"),
                    "vendor": purchase.get("EntityRef", {}).get("name", "unknown"),
                }
            )

        errors = []
        if "error" in qb_result or not qb_response:
            errors.append(qb_result.get("error", "Unknown QuickBooks error"))

        self.audit_logger.log_quickbooks_integration(
            correlation_id, qb_entries, processing_time, errors if errors else None
        )

    def _create_processing_summary(
        self,
        enhanced_expense: MultiCategoryExpense,
        rule_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create processing summary for audit completion."""
        total_deductible = sum(
            float(item.deductible_amount)
            for item in enhanced_expense.categorized_line_items
        )

        return {
            "vendor": enhanced_expense.vendor_name,
            "total_amount": enhanced_expense.total_amount,
            "categories_count": len(
                {item.category for item in enhanced_expense.categorized_line_items}
            ),
            "rules_applied": len(rule_results),
            "qb_entries_created": 1,  # Current implementation creates single purchase
            "deductible_amount": total_deductible,
            "entity_type": "sole_proprietorship",
            "tax_form": "T2125",
            "compliance_notes": [
                result.get("compliance_note")
                for result in rule_results
                if result.get("compliance_note")
            ],
            "items_processed": len(enhanced_expense.categorized_line_items),
            "success_rate": 100.0,
            "average_confidence": sum(
                result.get("confidence_score", 0) for result in rule_results
            )
            / max(len(rule_results), 1),
        }


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

    # Add version argument
    parser.add_argument(
        "--version",
        action="version",
        version=f"quickexpense {__version__}",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth command
    auth_parser = subparsers.add_parser(
        "auth",
        help="Authenticate with QuickBooks",
        description="Run OAuth flow to connect with QuickBooks Online",
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
        description="Check authentication, API connections, and configuration",
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
    upload_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with audit trail information",
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
