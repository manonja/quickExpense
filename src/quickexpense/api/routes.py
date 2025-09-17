"""Main API routes."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status

from quickexpense.core.dependencies import GeminiServiceDep, QuickBooksServiceDep
from quickexpense.models import (
    Expense,
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
