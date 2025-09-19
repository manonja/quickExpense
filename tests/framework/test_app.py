"""FastAPI test app with dependency injection mocking."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quickexpense.api.routes import router
from quickexpense.core.dependencies import (
    get_gemini_service,
    get_quickbooks_service,
)
from quickexpense.models.quickbooks_oauth import QuickBooksTokenInfo


class MockQuickBooksService:
    """Mock QuickBooks service for testing."""

    def __init__(self) -> None:
        self.search_vendor = AsyncMock()
        self.create_vendor = AsyncMock()
        self.get_expense_accounts = AsyncMock()
        self.get_bank_accounts = AsyncMock()
        self.create_expense = AsyncMock()
        self.test_connection = AsyncMock()


class MockGeminiService:
    """Mock Gemini service for testing."""

    def __init__(self) -> None:
        self.extract_receipt_data = AsyncMock()


@pytest.fixture
def mock_quickbooks_service() -> MockQuickBooksService:
    """Create a mock QuickBooks service."""
    return MockQuickBooksService()


@pytest.fixture
def mock_gemini_service() -> MockGeminiService:
    """Create a mock Gemini service."""
    return MockGeminiService()


@pytest.fixture
def test_app(
    mock_quickbooks_service: MockQuickBooksService,
    mock_gemini_service: MockGeminiService,
) -> FastAPI:
    """Create a FastAPI test app with mocked dependencies."""
    app = FastAPI(title="QuickExpense Test API")

    # Include the main router
    app.include_router(router)

    # Override dependencies with mocks
    app.dependency_overrides[get_quickbooks_service] = lambda: mock_quickbooks_service
    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini_service

    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    """Create a test client with mocked dependencies."""
    return TestClient(test_app)


@pytest.fixture
def sample_oauth_tokens() -> QuickBooksTokenInfo:
    """Create sample OAuth tokens for testing."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    return QuickBooksTokenInfo(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        access_token_expires_at=now + timedelta(seconds=3600),
        refresh_token_expires_at=now + timedelta(seconds=8640000),
    )
