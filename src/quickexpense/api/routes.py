"""Main API routes."""

from __future__ import annotations

import base64
import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from quickexpense.core.dependencies import (
    GeminiServiceDep,
    MultiAgentOrchestratorDep,
    QuickBooksServiceDep,
)
from quickexpense.models import (
    AgentResultResponse,
    Expense,
    MultiAgentReceiptResponse,
    ReceiptExtractionRequest,
    ReceiptExtractionResponse,
)
from quickexpense.services.quickbooks import (
    AccountInfo,
    QuickBooksError,
    VendorSearchResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["expenses"])

# Supported file formats (matching CLI)
SUPPORTED_FORMATS = {
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


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "QuickExpense API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense: Expense,
    service: QuickBooksServiceDep,
) -> dict[str, Any]:
    """Create a new expense in QuickBooks."""
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks service not available. Please authenticate first.",
        )
    try:
        result = await service.create_expense(expense)
        return {
            "status": "success",
            "message": f"Expense created for {expense.vendor_name}",
            "data": result,
        }
    except QuickBooksError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create expense: {e}",
        ) from e


@router.get("/vendors/{vendor_name}")
async def search_vendor(
    vendor_name: str,
    service: QuickBooksServiceDep,
) -> list[VendorSearchResult]:
    """Search for vendors by name."""
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks service not available. Please authenticate first.",
        )
    try:
        return await service.search_vendor(vendor_name)
    except QuickBooksError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to search vendor: {e}",
        ) from e


@router.post("/vendors", status_code=status.HTTP_201_CREATED)
async def create_vendor(
    vendor_name: str,
    service: QuickBooksServiceDep,
) -> VendorSearchResult:
    """Create a new vendor."""
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks service not available. Please authenticate first.",
        )
    try:
        return await service.create_vendor(vendor_name)
    except QuickBooksError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create vendor: {e}",
        ) from e


@router.get("/accounts/expense")
async def get_expense_accounts(
    service: QuickBooksServiceDep,
) -> list[AccountInfo]:
    """Get all expense accounts."""
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks service not available. Please authenticate first.",
        )
    try:
        return await service.get_expense_accounts()
    except QuickBooksError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get expense accounts: {e}",
        ) from e


@router.get("/test-connection")
async def test_connection(
    service: QuickBooksServiceDep,
) -> dict[str, Any]:
    """Test QuickBooks connection."""
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks service not available. Please authenticate first.",
        )
    try:
        result = await service.test_connection()
        return {"status": "connected", "company": result}
    except QuickBooksError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"QuickBooks connection failed: {e}",
        ) from e


@router.post("/receipts/extract", response_model=ReceiptExtractionResponse)
async def extract_receipt(
    request: ReceiptExtractionRequest,
    gemini_service: GeminiServiceDep,
) -> ReceiptExtractionResponse:
    """Extract expense data from a receipt file (image or PDF) using Gemini AI.

    Args:
        request: Contains base64 encoded file (image or PDF) and optional context
        gemini_service: Gemini AI service for receipt processing

    Returns:
        ReceiptExtractionResponse with extracted receipt and expense data
    """
    try:
        # Start timing
        start_time = time.time()

        # Extract receipt data (now supports both images and PDFs)
        receipt = await gemini_service.extract_receipt_data(
            request.image_base64,  # Can be image or PDF base64
            request.additional_context,
        )

        # Convert to expense format
        expense_data = receipt.to_expense(request.category)

        # Calculate processing time
        processing_time = time.time() - start_time

        return ReceiptExtractionResponse(
            receipt=receipt,
            expense_data=expense_data,
            processing_time=processing_time,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract receipt data: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error during receipt extraction")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/receipts/process-file", response_model=MultiAgentReceiptResponse)
async def process_receipt_file(
    receipt: Annotated[
        UploadFile, File(description="Receipt file (JPEG, PNG, PDF, HEIC)")
    ],
    orchestrator: MultiAgentOrchestratorDep,
    additional_context: Annotated[
        str, Form(description="Additional context")
    ] = "Business expense receipt",
) -> MultiAgentReceiptResponse:
    """Process a receipt file directly using multi-agent system.

    This endpoint accepts file uploads directly (no base64 encoding needed)
    and processes them through the 3-agent system for CRA compliance.
    Supports all common receipt formats: JPEG, PNG, PDF, HEIC/HEIF, etc.

    Example usage:
        curl -X POST http://localhost:8000/api/v1/receipts/process-file \
            -F "receipt=@/path/to/receipt.jpg" \
            -F "additional_context=Business meal with client"

    Args:
        receipt: The uploaded receipt file
        orchestrator: Multi-agent orchestrator service (injected)
        additional_context: Optional context about the expense

    Returns:
        MultiAgentReceiptResponse with consensus results and agent breakdown
    """
    try:
        # Validate file
        if not receipt.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided"
            )

        # Check file extension
        file_ext = f".{receipt.filename.split('.')[-1]}".lower()
        if file_ext not in SUPPORTED_FORMATS:
            supported = ", ".join(sorted(SUPPORTED_FORMATS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file_ext}'. Supported: {supported}",
            )

        # Read file content
        file_content = await receipt.read()

        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            size_mb = len(file_content) / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large ({size_mb:.1f}MB). Maximum size: 10MB",
            )

        # Convert to base64 for processing
        file_base64 = base64.b64encode(file_content).decode("utf-8")

        logger.info(
            "Processing receipt file: filename=%s, size=%d bytes, format=%s",
            receipt.filename,
            len(file_content),
            file_ext,
        )

        # Process receipt through multi-agent system
        consensus_result = await orchestrator.process_receipt(
            file_base64=file_base64,
            additional_context=additional_context,
        )

        # Convert ConsensusResult to response model (same as base64 endpoint)

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

        response = MultiAgentReceiptResponse(
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
            deductibility_percentage=final_data.get("deductibility_percentage"),
            qb_account=final_data.get("qb_account"),
            ita_section=final_data.get("ita_section"),
            audit_risk=final_data.get("audit_risk"),
            # Tax calculations
            calculated_gst_hst=final_data.get("calculated_gst_hst"),
            deductible_amount=final_data.get("deductible_amount"),
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

        logger.info(
            "Receipt processed: %s, conf=%.2f, time=%.2f, flags=%d",
            receipt.filename,
            consensus_result.overall_confidence,
            consensus_result.processing_time,
            len(consensus_result.flags_for_review),
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        logger.warning("File processing validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process receipt file: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error during file processing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during file processing",
        ) from e
