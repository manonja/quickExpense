"""Main API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, status

from quickexpense.core.dependencies import QuickBooksServiceDep
from quickexpense.models import Expense
from quickexpense.services.quickbooks import QuickBooksError

if TYPE_CHECKING:
    from quickexpense.services.quickbooks import AccountInfo, VendorSearchResult

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
