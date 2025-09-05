"""Tests for Gemini AI service."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from quickexpense.models.receipt import ExtractedReceipt, PaymentMethod
from quickexpense.services.gemini import GeminiService


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.gemini_api_key = "test-api-key"
    settings.gemini_model = "gemini-2.0-flash-exp"
    settings.gemini_timeout = 30
    return settings


@pytest.fixture
def gemini_service(mock_settings: MagicMock) -> GeminiService:
    """Create a GeminiService instance with mocked dependencies."""
    with (
        patch("quickexpense.services.gemini.genai.configure"),
        patch("quickexpense.services.gemini.genai.GenerativeModel") as mock_model,
    ):
        service = GeminiService(mock_settings)
        service.model = mock_model.return_value
        return service


@pytest.fixture
def sample_receipt_response() -> dict[str, Any]:
    """Sample receipt data that Gemini might return."""
    return {
        "vendor_name": "Coffee Shop",
        "vendor_address": "123 Main St",
        "vendor_phone": "555-1234",
        "transaction_date": "2024-01-15",
        "receipt_number": "REC-001",
        "payment_method": "credit_card",
        "line_items": [
            {
                "description": "Cappuccino",
                "quantity": 1,
                "unit_price": 4.50,
                "total_price": 4.50,
            },
            {
                "description": "Croissant",
                "quantity": 2,
                "unit_price": 3.00,
                "total_price": 6.00,
            },
        ],
        "subtotal": 10.50,
        "tax_amount": 0.84,
        "tip_amount": 2.00,
        "total_amount": 13.34,
        "currency": "USD",
        "notes": "Business meeting",
        "confidence_score": 0.95,
    }


@pytest.mark.asyncio
async def test_extract_receipt_data_success(
    gemini_service: GeminiService, sample_receipt_response: dict[str, Any]
) -> None:
    """Test successful receipt data extraction."""
    # Mock the Gemini response
    mock_response = MagicMock()
    mock_response.text = str(sample_receipt_response).replace("'", '"')
    gemini_service.model.generate_content = MagicMock(return_value=mock_response)

    # Test base64 image (1x1 white pixel)
    test_image = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
        "60e6kgAAAABJRU5ErkJggg=="
    )

    # Extract receipt data
    result = await gemini_service.extract_receipt_data(test_image)

    # Assertions
    assert isinstance(result, ExtractedReceipt)
    assert result.vendor_name == "Coffee Shop"
    assert result.vendor_address == "123 Main St"
    assert result.payment_method == PaymentMethod.CREDIT_CARD
    assert len(result.line_items) == 2
    assert result.subtotal == Decimal("10.50")
    assert result.tax_amount == Decimal("0.84")
    assert result.tip_amount == Decimal("2.00")
    assert result.total_amount == Decimal("13.34")
    assert result.confidence_score == 0.95


@pytest.mark.asyncio
async def test_extract_receipt_data_with_context(
    gemini_service: GeminiService, sample_receipt_response: dict[str, Any]
) -> None:
    """Test receipt extraction with additional context."""
    mock_response = MagicMock()
    mock_response.text = str(sample_receipt_response).replace("'", '"')
    gemini_service.model.generate_content = MagicMock(return_value=mock_response)

    test_image = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
        "60e6kgAAAABJRU5ErkJggg=="
    )
    context = "This is a business expense from a client meeting"

    await gemini_service.extract_receipt_data(test_image, context)

    # Verify the prompt includes context
    call_args = gemini_service.model.generate_content.call_args[0][0]
    assert context in call_args[0]  # First argument is the prompt


@pytest.mark.asyncio
async def test_extract_receipt_data_no_response(
    gemini_service: GeminiService,
) -> None:
    """Test handling when Gemini returns no response."""
    mock_response = MagicMock()
    mock_response.text = None
    gemini_service.model.generate_content = MagicMock(return_value=mock_response)

    test_image = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
        "60e6kgAAAABJRU5ErkJggg=="
    )

    with pytest.raises(ValueError, match="No response from Gemini model"):
        await gemini_service.extract_receipt_data(test_image)


@pytest.mark.asyncio
async def test_extract_receipt_data_invalid_json(
    gemini_service: GeminiService,
) -> None:
    """Test handling of invalid JSON response."""
    mock_response = MagicMock()
    mock_response.text = "This is not valid JSON"
    gemini_service.model.generate_content = MagicMock(return_value=mock_response)

    test_image = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
        "60e6kgAAAABJRU5ErkJggg=="
    )

    with pytest.raises(ValueError, match="Failed to parse Gemini response as JSON"):
        await gemini_service.extract_receipt_data(test_image)


@pytest.mark.asyncio
async def test_extract_receipt_data_invalid_image(
    gemini_service: GeminiService,
) -> None:
    """Test handling of invalid base64 image."""
    invalid_image = "not-valid-base64"

    with pytest.raises(ValueError, match="Failed to decode or process image"):
        await gemini_service.extract_receipt_data(invalid_image)


def test_build_extraction_prompt(gemini_service: GeminiService) -> None:
    """Test prompt building without context."""
    prompt = gemini_service._build_extraction_prompt(None)  # noqa: SLF001

    assert "Extract all information from this receipt image" in prompt
    assert "vendor_name" in prompt
    assert "line_items" in prompt
    assert "Important instructions:" in prompt


def test_build_extraction_prompt_with_context(
    gemini_service: GeminiService,
) -> None:
    """Test prompt building with additional context."""
    context = "This is a business lunch expense"
    prompt = gemini_service._build_extraction_prompt(context)  # noqa: SLF001

    assert "Additional context: This is a business lunch expense" in prompt


def test_receipt_to_expense_conversion(
    sample_receipt_response: dict[str, Any],
) -> None:
    """Test converting ExtractedReceipt to expense format."""
    receipt = ExtractedReceipt(**sample_receipt_response)
    expense_data = receipt.to_expense("Travel")

    assert expense_data["vendor_name"] == "Coffee Shop"
    assert expense_data["amount"] == Decimal("13.34")
    assert expense_data["currency"] == "USD"
    assert expense_data["category"] == "Travel"
    assert expense_data["payment_account"] == "credit_card"
    assert "Cappuccino, Croissant" in expense_data["description"]
    assert expense_data["notes"] == "Business meeting"
