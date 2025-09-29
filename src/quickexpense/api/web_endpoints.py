"""Web UI API endpoints for QuickExpense."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse

from quickexpense.core.dependencies import (
    BusinessRulesEngineDep,
    GeminiServiceDep,
    OAuthManagerDep,
    QuickBooksServiceDep,
    get_oauth_manager,
)
from quickexpense.models.business_rules import ExpenseContext
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
async def upload_receipt(
    gemini_service: GeminiServiceDep,
    quickbooks_service: QuickBooksServiceDep,
    business_rules_engine: BusinessRulesEngineDep,
    file: UploadFile = File(..., description="Receipt file (JPEG, PNG, PDF, HEIC)"),  # noqa: B008
    category: str = Form(default="", description="Optional expense category"),
    additional_context: str = Form(
        default="", description="Additional context for processing"
    ),
    dry_run: bool = Form(default=False, description="Preview processing without creating expenses"),
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
            transaction_date=receipt.transaction_date,
            currency=receipt.currency,
            vendor_address=getattr(receipt, "vendor_address", None),
            postal_code=None,
            payment_method=payment_method,
            business_purpose=None,
            location=None,
        )
        
        # Apply business rules to line items
        rule_results = business_rules_engine.categorize_line_items(
            receipt.line_items, context
        )
        
        # Convert rule results to format needed for response and QuickBooks
        rule_data = []
        total_deductible = 0.0
        categories_used = set()
        
        for i, result in enumerate(rule_results):
            # Get original line item for description and amount (matching CLI logic)
            original_item = receipt.line_items[i] if i < len(receipt.line_items) else {}
            
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
                item_amount = float(getattr(original_item, "total_price", 
                                          getattr(original_item, "unit_price", 0)))
            elif isinstance(original_item, dict):
                # Dictionary format
                item_amount = float(original_item.get("amount", 0))
            else:
                item_amount = 0.0
            
            rule_info = {
                "description": description,
                "rule_name": result.rule_applied.name if result.rule_applied else "Default",
                "rule_applied": result.rule_applied.id if result.rule_applied else "default",
                "category": result.category,
                "qb_account": result.account_mapping,
                "amount": item_amount,
                "deductible_percentage": result.deductibility_percentage,
                "tax_treatment": result.tax_treatment,
                "confidence": result.confidence_score,
            }
            rule_data.append(rule_info)
            
            # Calculate deductible amount
            deductible_amount = item_amount * result.deductibility_percentage / 100.0
            total_deductible += deductible_amount
            categories_used.add(result.category)

        # Create expenses for QuickBooks (use the first rule result for main expense)
        if rule_results:
            # Use the first categorized item as the primary expense
            primary_result = rule_results[0]
            from quickexpense.models.expense import Expense
            
            expense = Expense(
                vendor_name=receipt.vendor_name,
                amount=receipt.total_amount,  # Use total amount, not individual line item
                date=receipt.transaction_date,
                currency=receipt.currency,
                category=primary_result.category,
            )
        else:
            # Fallback if no rules applied
            from quickexpense.models.expense import Expense
            
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
            "message": "DRY RUN - No expense created in QuickBooks" if dry_run else None,
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
