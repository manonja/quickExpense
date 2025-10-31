"""Web UI API endpoints for QuickExpense."""

# ruff: noqa: B008

from __future__ import annotations

import base64
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:
    from quickexpense.core.dependencies import (
        BusinessRulesEngineDep,
        GeminiServiceDep,
        MultiAgentOrchestratorDep,
        OAuthManagerDep,
        QuickBooksServiceDep,
    )
else:
    # Import actual dependencies for runtime
    from quickexpense.core.dependencies import (  # noqa: TCH001
        BusinessRulesEngineDep,
        GeminiServiceDep,
        MultiAgentOrchestratorDep,
        OAuthManagerDep,
        QuickBooksServiceDep,
    )
from quickexpense.models.business_rules import ExpenseContext
from quickexpense.models.multi_agent import (
    AgentResultResponse,
    MultiAgentReceiptResponse,
)
from quickexpense.services.file_processor import FileProcessorService
from quickexpense.services.quickbooks import QuickBooksError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/web", tags=["web"])

# Supported file formats (images and PDFs)
SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".pdf",
    ".heic",
    ".heif",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.get("/auth-status")
async def get_auth_status(
    oauth_manager: OAuthManagerDep,
    quickbooks_service: QuickBooksServiceDep,
) -> dict[str, Any]:
    """Get QuickBooks authentication status.

    Returns:
        dict with authenticated boolean and company_id if available
    """
    try:
        # Check if we have valid tokens
        if not oauth_manager.tokens or oauth_manager.tokens.refresh_token_expired:
            return {
                "authenticated": False,
                "company_id": None,
                "message": "No valid authentication tokens",
            }

        # Check if QuickBooks service is available
        if quickbooks_service is None:
            return {
                "authenticated": False,
                "company_id": None,
                "message": (
                    "QuickBooks client not initialized - authentication required"
                ),
            }

        # Test the connection to ensure tokens work
        try:
            company_info = await quickbooks_service.test_connection()
            return {
                "authenticated": True,
                "company_id": company_info.get("id"),
                "company_name": company_info.get("name"),
                "message": "Connected to QuickBooks",
            }
        except QuickBooksError:
            return {
                "authenticated": False,
                "company_id": None,
                "message": "Authentication tokens invalid or expired",
            }
    except Exception:
        logger.exception("Error checking auth status")
        return {
            "authenticated": False,
            "company_id": None,
            "message": "Error checking authentication status",
        }


@router.get("/auth-url")
async def get_auth_url(oauth_manager: OAuthManagerDep) -> dict[str, str]:
    """Get QuickBooks OAuth authorization URL.

    Returns:
        dict with authorization URL
    """
    try:
        # Generate a simple state parameter for CSRF protection
        import secrets

        state = secrets.token_urlsafe(32)

        auth_url = oauth_manager.get_authorization_url(state)
        return {
            "auth_url": auth_url,
            "state": state,
            "message": "Authorization URL generated",
        }
    except Exception as e:
        logger.error("Error generating auth URL: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authorization URL",
        ) from e


@router.get("/callback")
async def oauth_callback(
    oauth_manager: OAuthManagerDep,
    code: str = Query(..., description="Authorization code from QuickBooks"),
    _state: str = Query(..., description="State parameter for CSRF protection"),
    realm_id: str = Query(..., description="QuickBooks company ID", alias="realmId"),
) -> HTMLResponse:
    """Handle OAuth callback from QuickBooks.

    This endpoint processes the OAuth callback and closes the popup window.
    """
    try:
        # Exchange authorization code for tokens
        tokens = await oauth_manager.exchange_code_for_tokens(
            authorization_code=code, realm_id=realm_id
        )

        # Update the token store with company ID
        from quickexpense.core.dependencies import (
            initialize_quickbooks_client_after_oauth,
        )
        from quickexpense.services.token_store import TokenStore

        token_store = TokenStore("data/tokens.json")
        token_data = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
            "company_id": realm_id,
            "created_at": tokens.access_token_expires_at.isoformat(),
            "saved_at": tokens.access_token_expires_at.isoformat(),
        }
        token_store.save_tokens(token_data)

        # Initialize QuickBooks client now that we have tokens and company ID
        await initialize_quickbooks_client_after_oauth(realm_id)

        logger.info(
            "OAuth callback successful, tokens saved and QuickBooks client initialized"
        )

        # Return HTML that closes the popup and notifies parent window
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{
                    font-family: 'Geist', system-ui, sans-serif;
                    text-align: center;
                    padding: 2rem;
                    background: linear-gradient(
                        135deg, #fdf2f8 30%, #fff7ed 20%, #fdf2f8 40%
                    );
                    color: #404040;
                }}
                .success {{
                    background: white;
                    padding: 2rem;
                    border-radius: 1.5rem;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    max-width: 400px;
                    margin: 0 auto;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <h2>✅ Connected to QuickBooks!</h2>
                <p>Authentication successful. This window will close automatically.</p>
            </div>
            <script>
                // Notify parent window and close popup
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'oauth_success',
                        authenticated: true,
                        company_id: '{realm_id}'
                    }}, '*');
                }}
                setTimeout(() => window.close(), 2000);
            </script>
        </body>
        </html>
        """

        return HTMLResponse(content=html_content)

    except Exception:
        logger.exception("OAuth callback error")

        # Return error HTML that notifies parent window
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {
                    font-family: 'Geist', system-ui, sans-serif;
                    text-align: center;
                    padding: 2rem;
                    background: linear-gradient(
                        135deg, #fdf2f8 30%, #fff7ed 20%, #fdf2f8 40%
                    );
                    color: #404040;
                }
                .error {
                    background: white;
                    padding: 2rem;
                    border-radius: 1.5rem;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    max-width: 400px;
                    margin: 0 auto;
                    border-left: 4px solid #ef4444;
                }
            </style>
        </head>
        <body>
            <div class="error">
                <h2>❌ Authentication Failed</h2>
                <p>Please try connecting again.</p>
            </div>
            <script>
                if (window.opener) {
                    window.opener.postMessage({
                        type: 'oauth_error',
                        error: 'Authentication failed'
                    }, '*');
                }
                setTimeout(() => window.close(), 3000);
            </script>
        </body>
        </html>
        """

        return HTMLResponse(content=html_content, status_code=400)


def _validate_file(file: UploadFile) -> None:
    """Validate uploaded file."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided"
        )

    # Check file extension
    file_extension = None
    if "." in file.filename:
        file_extension = "." + file.filename.split(".")[-1].lower()

    if file_extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file format. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            ),
        )


async def _process_file_content(file: UploadFile) -> str:
    """Process file and return base64 content."""
    # Read file content
    file_content = await file.read()

    # Check file size
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    # Process file through FileProcessorService if needed (for PDFs)
    file_processor = FileProcessorService()
    processed_file = await file_processor.process_file(file_content)
    return processed_file.content


@router.post("/upload-receipt")
async def upload_receipt(  # noqa: C901, PLR0912, PLR0915
    gemini_service: GeminiServiceDep,
    quickbooks_service: QuickBooksServiceDep,
    business_rules_engine: BusinessRulesEngineDep,
    file: UploadFile = File(..., description="Receipt file (JPEG, PNG, PDF, HEIC)"),
    category: str = Form(default="", description="Optional expense category"),
    additional_context: str = Form(
        default="", description="Additional context for processing"
    ),
    dry_run: bool = Form(  # noqa: FBT001
        default=False, description="Preview processing without creating expenses"
    ),
) -> dict[str, Any]:
    """Upload and process a receipt file.

    This endpoint replicates the CLI upload functionality:
    1. Validates file format and size
    2. Extracts receipt data using Gemini AI
    3. Applies business rules for categorization
    4. Creates expense in QuickBooks
    5. Returns detailed results matching CLI format
    """
    start_time = time.time()

    try:
        # Check if QuickBooks service is available
        if quickbooks_service is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "QuickBooks authentication required. "
                    "Please connect to QuickBooks first."
                ),
            )

        # Validate and process file
        _validate_file(file)
        file_base64 = await _process_file_content(file)

        # Extract receipt data using Gemini
        logger.info("Extracting data from receipt: %s", file.filename)
        receipt = await gemini_service.extract_receipt_data(
            file_base64, additional_context
        )

        # Apply business rules for categorization
        logger.info("Applying business rules for categorization...")

        # Create expense context for business rules (matching CLI logic)
        payment_method = str(getattr(receipt, "payment_method", "unknown"))
        if "<" in payment_method and ">" in payment_method:
            # Handle format like "<PaymentMethod.DEBIT_CARD: 'debit_card'>"
            payment_method = payment_method.split("'")[-2]

        context = ExpenseContext(
            vendor_name=receipt.vendor_name,
            total_amount=receipt.total_amount,
            transaction_date=datetime.combine(
                receipt.transaction_date, datetime.min.time()
            ),
            currency=receipt.currency,
            vendor_address=getattr(receipt, "vendor_address", None),
            postal_code=None,
            payment_method=payment_method,
            business_purpose=None,
            location=None,
        )

        # Check if this is a local restaurant (matching CLI logic)
        is_local_restaurant = _is_local_restaurant(
            receipt.vendor_name, receipt.line_items
        )

        if is_local_restaurant:
            # Use restaurant consolidation logic (matching CLI)
            rule_data, total_deductible = _process_restaurant_consolidated(
                receipt.line_items, float(receipt.tax_amount), float(receipt.tip_amount)
            )
            categories_used = {"Meals & Entertainment", "Tax-GST/HST"}
        else:
            # Apply regular business rules to line items
            rule_results = business_rules_engine.categorize_line_items(
                receipt.line_items, context
            )

            # Convert rule results to format needed for response and QuickBooks
            rule_data = []
            total_deductible = 0.0
            categories_used = set()

            for i, result in enumerate(rule_results):
                # Get original line item for description and amount (matching CLI logic)
                original_item: Any = (
                    receipt.line_items[i] if i < len(receipt.line_items) else {}
                )

                # Get description from original item
                if hasattr(original_item, "description"):
                    description = getattr(original_item, "description", f"Item {i+1}")
                elif isinstance(original_item, dict):
                    description = original_item.get("description", f"Item {i+1}")
                else:
                    description = f"Item {i+1}"

                # Get amount from original item (RuleResult doesn't have amount)
                if hasattr(original_item, "total_price"):
                    # LineItem model - use total_price, fallback to unit_price
                    item_amount = float(
                        getattr(
                            original_item,
                            "total_price",
                            getattr(original_item, "unit_price", 0),
                        )
                    )
                elif isinstance(original_item, dict):
                    # Dictionary format
                    item_amount = float(original_item.get("amount", 0))
                else:
                    item_amount = 0.0

                rule_info = {
                    "description": description,
                    "rule_name": (
                        result.rule_applied.name if result.rule_applied else "Default"
                    ),
                    "rule_applied": (
                        result.rule_applied.id if result.rule_applied else "default"
                    ),
                    "category": result.category,
                    "qb_account": result.account_mapping,
                    "amount": item_amount,
                    "deductible_percentage": result.deductibility_percentage,
                    "tax_treatment": result.tax_treatment,
                    "confidence": result.confidence_score,
                }
                rule_data.append(rule_info)

                # Calculate deductible amount
                deductible_amount = (
                    item_amount * result.deductibility_percentage / 100.0
                )
                total_deductible += deductible_amount
                categories_used.add(result.category)

        # Create expenses for QuickBooks
        from quickexpense.models.expense import Expense

        if rule_data:
            # Use the first rule for the primary expense category
            primary_category = rule_data[0]["category"]
            expense = Expense(
                vendor_name=receipt.vendor_name,
                amount=receipt.total_amount,  # Use total amount, not individual line
                date=receipt.transaction_date,
                currency=receipt.currency,
                category=primary_category,
            )
        else:
            # Fallback if no rules applied
            expense = Expense(
                vendor_name=receipt.vendor_name,
                amount=receipt.total_amount,
                date=receipt.transaction_date,
                currency=receipt.currency,
                category=category or "General",
            )

        # Create in QuickBooks (or skip if dry-run)
        if dry_run:
            logger.info("DRY RUN - Skipping QuickBooks expense creation")
            qb_results = [
                {
                    "id": "DRY_RUN",
                    "category": expense.category,
                    "amount": float(expense.amount),
                    "deductible_percentage": (
                        rule_data[0]["deductible_percentage"] if rule_data else 100
                    ),
                }
            ]
        else:
            logger.info("Creating expense in QuickBooks...")
            qb_result = await quickbooks_service.create_expense(expense)
            qb_results = [
                {
                    "id": qb_result.get("id"),
                    "category": expense.category,
                    "amount": float(expense.amount),
                    "deductible_percentage": (
                        rule_data[0]["deductible_percentage"] if rule_data else 100
                    ),
                }
            ]

        # Calculate processing time
        processing_time = time.time() - start_time

        # Calculate tax deductibility summary
        total_amount = float(receipt.total_amount)
        deductibility_rate = (
            (total_deductible / total_amount * 100) if total_amount > 0 else 0
        )

        # Get payment account info
        payment_account = "cash"  # Default for now

        # Format response to match CLI output
        response = {
            "status": "success",
            "dry_run": dry_run,
            "message": (
                "DRY RUN - No expense created in QuickBooks" if dry_run else None
            ),
            "receipt_info": {
                "filename": file.filename,
                "vendor_name": receipt.vendor_name,
                "date": receipt.transaction_date.isoformat(),
                "total_amount": float(receipt.total_amount),
                "tax_amount": float(receipt.tax_amount) if receipt.tax_amount else 0.0,
                "currency": receipt.currency,
            },
            "business_rules": {
                "applied_rules": rule_data,
                "total_categories": len(rule_data),
            },
            "tax_deductibility": {
                "total_amount": f"{total_amount:.2f}",
                "deductible_amount": f"{total_deductible:.2f}",
                "deductibility_rate": f"{deductibility_rate:.1f}",
            },
            "enhanced_expense": {
                "vendor_name": receipt.vendor_name,
                "items_count": len(receipt.line_items),
                "categories_count": len(rule_data),
                "rules_applied": len(rule_data),
                "payment": payment_account,
            },
            "quickbooks": {
                "expenses_created": len(qb_results),
                "expense_ids": [result["id"] for result in qb_results],
                "details": qb_results,
            },
            "processing_time": round(processing_time, 2),
        }

        logger.info(
            "Successfully processed receipt %s: %d expenses created",
            file.filename,
            len(qb_results),
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except QuickBooksError as e:
        logger.error("QuickBooks error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"QuickBooks error: {e}"
        ) from e
    except Exception as e:
        logger.exception("Unexpected error processing receipt")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred processing the receipt",
        ) from e


def _format_line_items_as_rules(
    line_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert orchestrator line_items to business rules format for UI display.

    Args:
        line_items: Processed line items from orchestrator with citations

    Returns:
        List of rule dictionaries compatible with UI expectations
    """
    if not line_items:
        return []

    rules = []
    for item in line_items:
        rule = {
            "description": item.get(
                "original_description", f"Line {item.get('line_number', '?')}"
            ),
            "rule_name": "CRArulesAgent Line-Item Processing",
            "rule_applied": "agent_line_item_categorization",
            "category": item.get("category", "Uncategorized"),
            "qb_account": item.get("qb_account", "Unknown"),
            "amount": float(item.get("original_amount", 0)),
            "deductible_percentage": item.get("deductibility_percent", 0),
            "tax_treatment": "CRA rules applied",
            "confidence": 0.7,  # Placeholder - not in current line_item structure
            # Include citations for future UI rendering
            "citations": item.get("citations", []),
        }
        rules.append(rule)

    return rules


@router.post("/upload-receipt-agents")
async def upload_receipt_with_agents(  # noqa: C901, PLR0915
    orchestrator: MultiAgentOrchestratorDep,
    quickbooks_service: QuickBooksServiceDep,
    file: UploadFile = File(..., description="Receipt file (JPEG, PNG, PDF, HEIC)"),
    additional_context: str = Form(
        default="Business expense receipt",
        description="Additional context for processing",
    ),
    dry_run: bool = Form(  # noqa: FBT001
        default=False, description="Preview processing without creating expenses"
    ),
) -> dict[str, Any]:
    """Upload and process a receipt file using the multi-agent system.

    This endpoint provides agent-based processing as an alternative to the standard
    Gemini + business rules approach. It uses the 3-agent system:
    - DataExtractionAgent: Extracts receipt data using Gemini
    - CRArulesAgent: Applies Canadian tax rules using TogetherAI
    - TaxCalculatorAgent: Validates tax calculations using TogetherAI

    Mirrors the /api/v1/receipts/process-file endpoint but returns
    web-compatible format.
    """
    try:
        # Validate file (using same pattern as API endpoint)
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided"
            )

        # Check file extension
        file_ext = f".{file.filename.split('.')[-1]}".lower()
        if file_ext not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file_ext}'. Supported: {supported}",
            )

        # Read file content
        file_content = await file.read()

        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            size_mb = len(file_content) / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large ({size_mb:.1f}MB). Maximum size: 10MB",
            )

        # Convert to base64 for processing (same as API endpoint)
        file_base64 = base64.b64encode(file_content).decode("utf-8")

        logger.info(
            (
                "Processing receipt file with agents: filename=%s, size=%d bytes, "
                "format=%s"
            ),
            file.filename,
            len(file_content),
            file_ext,
        )

        # Process receipt through multi-agent system (exact same call as API endpoint)
        consensus_result = await orchestrator.process_receipt(
            file_base64=file_base64,
            additional_context=additional_context,
        )

        # Convert to AgentResultResponse format (same as API endpoint)
        agent_results = [
            AgentResultResponse(
                agent_name=result.agent_name,
                success=result.success,
                confidence_score=result.confidence_score,
                processing_time=result.processing_time,
                error_message=result.error_message,
            )
            for result in consensus_result.agent_results
        ]

        # Extract key fields from final data
        final_data = consensus_result.final_data

        # Create MultiAgentReceiptResponse (same as API endpoint)
        agent_response = MultiAgentReceiptResponse(
            success=consensus_result.success,
            overall_confidence=consensus_result.overall_confidence,
            # Receipt data
            vendor_name=final_data.get("vendor_name"),
            transaction_date=final_data.get("transaction_date"),
            total_amount=final_data.get("total_amount"),
            subtotal=final_data.get("subtotal"),
            tax_amount=final_data.get("tax_amount"),
            # CRA categorization
            category=final_data.get("category"),
            deductibility_percentage=final_data.get("deductibility_rate"),
            qb_account=final_data.get("qb_account"),
            ita_section=final_data.get("ita_section"),
            audit_risk=final_data.get("audit_risk"),
            # Tax calculations
            calculated_gst_hst=final_data.get("calculated_gst_hst"),
            deductible_amount=final_data.get("total_deductible"),
            tax_validation_result=final_data.get("tax_validation_result"),
            # Processing metadata
            processing_time=consensus_result.processing_time,
            consensus_method=consensus_result.consensus_method,
            flags_for_review=consensus_result.flags_for_review,
            # Agent details
            agent_results=agent_results,
            agent_confidence_scores=final_data.get("agent_confidence_scores", {}),
            # Full data for advanced users
            full_data=final_data,
        )

        # Handle QuickBooks creation if not dry-run
        if not dry_run and quickbooks_service:
            try:
                # Create expense in QuickBooks
                from datetime import datetime

                from quickexpense.models.expense import Expense

                # Parse transaction date
                transaction_date_str = final_data.get("transaction_date")
                if transaction_date_str:
                    try:
                        transaction_date = datetime.fromisoformat(
                            transaction_date_str.replace("Z", "+00:00")
                        ).date()
                    except (ValueError, AttributeError):
                        transaction_date = datetime.now(UTC).date()
                else:
                    transaction_date = datetime.now(UTC).date()

                expense = Expense(
                    vendor_name=final_data.get("vendor_name", "Unknown Vendor"),
                    amount=final_data.get("total_amount", 0.0),
                    date=transaction_date,
                    currency=final_data.get("currency", "CAD"),
                    category=final_data.get("category", "General"),
                )

                logger.info("Creating expense in QuickBooks...")
                qb_result = await quickbooks_service.create_expense(expense)
                qb_expense_id = qb_result.get("id")
                logger.info("Created QuickBooks expense: %s", qb_expense_id)
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning("QuickBooks expense creation failed: %s", e)
                qb_expense_id = None
        else:
            qb_expense_id = "DRY_RUN" if dry_run else None

        # Transform to web-compatible format while preserving agent data
        response = {
            "status": "success",
            "dry_run": dry_run,
            "agent_mode": True,  # Flag to indicate agent processing was used
            "message": (
                "DRY RUN - No expense created in QuickBooks" if dry_run else None
            ),
            "receipt_info": {
                "filename": file.filename,
                "vendor_name": agent_response.vendor_name,
                "date": agent_response.transaction_date,
                "total_amount": float(agent_response.total_amount or 0),
                "tax_amount": float(agent_response.tax_amount or 0),
                "currency": final_data.get("currency", "CAD"),
            },
            "business_rules": {
                "applied_rules": _format_line_items_as_rules(
                    final_data.get("line_items", [])
                ),
                "total_categories": len(final_data.get("line_items", [])),
            },
            "tax_deductibility": {
                "total_amount": f"{float(agent_response.total_amount or 0):.2f}",
                "deductible_amount": (
                    f"{float(agent_response.deductible_amount or 0):.2f}"
                ),
                "deductibility_rate": (
                    f"{float(agent_response.deductibility_percentage or 0):.1f}"
                ),
            },
            "enhanced_expense": {
                "vendor_name": agent_response.vendor_name,
                "items_count": len(final_data.get("line_items", [])),
                "categories_count": 1 if agent_response.category else 0,
                "rules_applied": 1 if agent_response.category else 0,
                "payment": "unknown",
            },
            "quickbooks": {
                "expenses_created": (
                    1 if qb_expense_id and qb_expense_id != "DRY_RUN" else 0
                ),
                "expense_ids": [qb_expense_id] if qb_expense_id else [],
                "details": (
                    [
                        {
                            "id": qb_expense_id,
                            "category": agent_response.category,
                            "amount": float(agent_response.total_amount or 0),
                            "deductible_percentage": (
                                agent_response.deductibility_percentage
                            ),
                        }
                    ]
                    if qb_expense_id
                    else []
                ),
            },
            "processing_time": round(agent_response.processing_time, 2),
            # Rich agent data for enhanced UI display
            "agent_details": {
                "overall_confidence": agent_response.overall_confidence,
                "consensus_method": agent_response.consensus_method,
                "flags_for_review": agent_response.flags_for_review,
                "agent_results": [
                    {
                        "agent_name": result.agent_name,
                        "success": result.success,
                        "confidence_score": result.confidence_score,
                        "processing_time": result.processing_time,
                        "error_message": result.error_message,
                    }
                    for result in agent_response.agent_results
                ],
                "agent_breakdown": {
                    "data_extraction": {
                        "agent": "DataExtractionAgent",
                        "purpose": "Extract receipt data using Gemini AI",
                        "confidence": agent_response.agent_confidence_scores.get(
                            "DataExtractionAgent", 0.0
                        ),
                    },
                    "cra_rules": {
                        "agent": "CRArulesAgent",
                        "purpose": "Apply Canadian tax rules and categorization",
                        "confidence": agent_response.agent_confidence_scores.get(
                            "CRArulesAgent", 0.0
                        ),
                    },
                    "tax_calculation": {
                        "agent": "TaxCalculatorAgent",
                        "purpose": "Validate GST/HST calculations and tax treatment",
                        "confidence": agent_response.agent_confidence_scores.get(
                            "TaxCalculatorAgent", 0.0
                        ),
                    },
                },
                "full_agent_data": {
                    **agent_response.full_data,
                    # Explicitly include line items with citations for UI access
                    "line_items": final_data.get("line_items", []),
                },
            },
        }

        logger.info(
            "Receipt processed with agents: %s, conf=%.2f, time=%.2f, flags=%d",
            file.filename,
            agent_response.overall_confidence,
            agent_response.processing_time,
            len(agent_response.flags_for_review),
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        logger.warning("Agent processing validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process receipt with agents: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error during agent processing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during agent processing",
        ) from e


def _is_local_restaurant(vendor_name: str, line_items: list[Any]) -> bool:
    """Check if this is a local restaurant using business rules patterns."""
    # Check against local_restaurant_meal rule patterns
    restaurant_patterns = [
        "*pho*",
        "*pizza*",
        "*burger*",
        "*sushi*",
        "*grill*",
        "*express*",
        "*food*",
        "*noodle*",
        "*ramen*",
        "*taco*",
        "*sandwich*",
        "*coffee*",
        "*tea*",
        "*restaurant*",
        "*cafe*",
        "*bistro*",
        "*bar*",
        "*pub*",
        "*eatery*",
        "*kitchen*",
        "*diner*",
    ]

    food_keywords = [
        "sandwich",
        "salad",
        "rolls",
        "burger",
        "pizza",
        "noodle",
        "soup",
        "chicken",
        "beef",
        "pork",
        "shrimp",
        "fish",
        "rice",
        "pasta",
        "meal",
        "lunch",
        "dinner",
        "breakfast",
    ]

    # Check vendor name against patterns
    vendor_lower = vendor_name.lower()
    for pattern in restaurant_patterns:
        pattern_clean = pattern.strip("*")
        if pattern_clean in vendor_lower:
            return True

    # Check if line items contain food keywords
    food_item_count = 0
    for item in line_items:
        description = _get_item_description(item).lower()
        if any(keyword in description for keyword in food_keywords):
            food_item_count += 1

    # If most items are food items, likely a restaurant
    food_threshold = 0.6  # 60% of items must be food-related
    return len(line_items) > 0 and food_item_count / len(line_items) >= food_threshold


def _get_item_description(item: Any) -> str:  # noqa: ANN401
    """Safely extract item description."""
    if hasattr(item, "description"):
        description = getattr(item, "description", "")
        return str(description) if description is not None else ""
    if isinstance(item, dict):
        return str(item.get("description", ""))
    return ""


def _get_item_amount(item: Any) -> float:  # noqa: ANN401
    """Safely extract item amount."""
    if hasattr(item, "total_price"):
        return float(getattr(item, "total_price", 0))
    if hasattr(item, "unit_price"):
        return float(getattr(item, "unit_price", 0))
    if isinstance(item, dict):
        return float(item.get("amount", 0))
    return 0.0


def _process_restaurant_consolidated(
    line_items: list[Any], tax_amount: float, tip_amount: float
) -> tuple[list[dict[str, Any]], float]:
    """Process restaurant receipt with consolidated meal format."""
    # Calculate food items total
    food_total = sum(_get_item_amount(item) for item in line_items)

    # Calculate meal amount (food + tip combined)
    meal_amount = food_total + tip_amount
    meal_deductible = meal_amount * 0.5  # 50% deductible
    gst_deductible = tax_amount * 1.0  # GST is 100% deductible

    total_deductible = meal_deductible + gst_deductible

    # Create rule data matching CLI format
    rule_data = [
        {
            "description": "Restaurant meal consolidation",
            "rule_name": "Local Restaurant Meal",
            "rule_applied": "Local Restaurant Detection",
            "category": "Meals & Entertainment",
            "qb_account": "Travel - Meals & Entertainment",
            "amount": meal_amount,
            "deductible_percentage": 50,
            "tax_treatment": "meals_limitation",
            "confidence": 0.95,
        }
    ]

    if tax_amount > 0:
        rule_data.append(
            {
                "description": "GST - Input Tax Credit",
                "rule_name": "GST/HST Tax Charges",
                "rule_applied": "GST/HST Tax Charges",
                "category": "Tax-GST/HST",
                "qb_account": "GST/HST Paid on Purchases",
                "amount": tax_amount,
                "deductible_percentage": 100,
                "tax_treatment": "input_tax_credit",
                "confidence": 1.0,
            }
        )

    return rule_data, total_deductible
