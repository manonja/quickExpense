"""Tests for receipt processing routes."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status

from quickexpense.models.receipt import ExtractedReceipt, LineItem, PaymentMethod

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.fixture
def mock_gemini_service() -> MagicMock:
    """Create a mock Gemini service."""
    service = MagicMock()
    service.extract_receipt_data = AsyncMock()
    return service


@pytest.fixture
def sample_extracted_receipt() -> ExtractedReceipt:
    """Create a sample extracted receipt."""
    return ExtractedReceipt(
        vendor_name="Test Restaurant",
        vendor_address="456 Oak St",
        vendor_phone="555-5678",
        transaction_date="2024-01-20",
        receipt_number="INV-123",
        payment_method=PaymentMethod.CREDIT_CARD,
        line_items=[
            LineItem(
                description="Burger",
                quantity=Decimal("1"),
                unit_price=Decimal("15.00"),
                total_price=Decimal("15.00"),
            ),
            LineItem(
                description="Fries",
                quantity=Decimal("1"),
                unit_price=Decimal("5.00"),
                total_price=Decimal("5.00"),
            ),
        ],
        subtotal=Decimal("20.00"),
        tax_amount=Decimal("1.60"),
        tip_amount=Decimal("3.00"),
        total_amount=Decimal("24.60"),
        currency="USD",
        notes="Client lunch meeting",
        confidence_score=0.98,
    )


@pytest.mark.asyncio
async def test_extract_receipt_success(
    client: TestClient,
    mock_quickbooks_client: MagicMock,
    mock_gemini_service: MagicMock,
    sample_extracted_receipt: ExtractedReceipt,
) -> None:
    """Test successful receipt extraction."""
    # Mock dependencies
    mock_quickbooks_client.search_vendor = AsyncMock(return_value=[{"Id": "1"}])
    mock_gemini_service.extract_receipt_data.return_value = sample_extracted_receipt

    # Override dependencies
    from quickexpense.core.dependencies import get_gemini_service
    from quickexpense.main import app

    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini_service

    try:
        # Test data
        request_data = {
            "image_base64": (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
                "60e6kgAAAABJRU5ErkJggg=="
            ),
            "category": "Meals & Entertainment",
            "additional_context": "Business lunch with client",
        }

        # Make request
        response = client.post("/api/v1/receipts/extract", json=request_data)

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "receipt" in data
        assert "expense_data" in data
        assert "processing_time" in data
        assert data["receipt"]["vendor_name"] == "Test Restaurant"
        assert data["receipt"]["total_amount"] == "24.6"
        assert data["expense_data"]["category"] == "Meals & Entertainment"

    finally:
        # Clean up
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_receipt_vendor_not_found(
    client: TestClient,
    mock_quickbooks_client: MagicMock,
    mock_gemini_service: MagicMock,
    sample_extracted_receipt: ExtractedReceipt,
) -> None:
    """Test receipt extraction when vendor doesn't exist."""
    # Mock dependencies - vendor not found
    mock_quickbooks_client.search_vendor = AsyncMock(return_value=[])
    mock_quickbooks_client.create_vendor = AsyncMock(
        return_value={"Id": "2", "DisplayName": "Test Restaurant"}
    )
    mock_gemini_service.extract_receipt_data.return_value = sample_extracted_receipt

    # Override dependencies
    from quickexpense.core.dependencies import get_gemini_service
    from quickexpense.main import app

    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini_service

    try:
        request_data = {
            "image_base64": (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
                "60e6kgAAAABJRU5ErkJggg=="
            ),
            "category": "Travel",
        }

        response = client.post("/api/v1/receipts/extract", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        # Verify vendor was created
        mock_quickbooks_client.create_vendor.assert_called_once_with("Test Restaurant")

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_receipt_gemini_error(
    client: TestClient,
    mock_quickbooks_client: MagicMock,  # noqa: ARG001
    mock_gemini_service: MagicMock,
) -> None:
    """Test handling of Gemini extraction errors."""
    # Mock Gemini error
    mock_gemini_service.extract_receipt_data.side_effect = ValueError(
        "Invalid image format"
    )

    from quickexpense.core.dependencies import get_gemini_service
    from quickexpense.main import app

    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini_service

    try:
        request_data = {
            "image_base64": "invalid-base64",
            "category": "Office Supplies",
        }

        response = client.post("/api/v1/receipts/extract", json=request_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to extract receipt data" in response.json()["detail"]

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_receipt_quickbooks_error(
    client: TestClient,
    mock_quickbooks_client: MagicMock,
    mock_gemini_service: MagicMock,
    sample_extracted_receipt: ExtractedReceipt,
) -> None:
    """Test handling of QuickBooks errors during vendor lookup."""
    from quickexpense.services.quickbooks import QuickBooksError

    # Mock QuickBooks error
    mock_quickbooks_client.search_vendor.side_effect = QuickBooksError(
        "API rate limit exceeded"
    )
    mock_gemini_service.extract_receipt_data.return_value = sample_extracted_receipt

    from quickexpense.core.dependencies import get_gemini_service
    from quickexpense.main import app

    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini_service

    try:
        request_data = {
            "image_base64": (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
                "60e6kgAAAABJRU5ErkJggg=="
            ),
            "category": "Travel",
        }

        response = client.post("/api/v1/receipts/extract", json=request_data)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "QuickBooks error" in response.json()["detail"]

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_receipt_missing_fields(client: TestClient) -> None:
    """Test validation of missing required fields."""
    # Missing image_base64
    request_data = {
        "category": "Travel",
    }

    response = client.post("/api/v1/receipts/extract", json=request_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Missing category
    request_data = {
        "image_base64": (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
            "60e6kgAAAABJRU5ErkJggg=="
        ),
    }

    response = client.post("/api/v1/receipts/extract", json=request_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
