"""Pytest configuration and fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from quickexpense.core.config import Settings, get_settings
from quickexpense.core.dependencies import set_oauth_manager, set_quickbooks_client
from quickexpense.main import create_app
from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
)
from quickexpense.services.quickbooks import QuickBooksClient
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from quickexpense.services.token_store import TokenStore

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        qb_base_url="https://sandbox-quickbooks.api.intuit.com",
        qb_client_id="test_client_id",
        qb_client_secret="test_client_secret",
        qb_redirect_uri="http://localhost:8000/callback",
        qb_company_id="test_company_id",
        gemini_api_key="test_gemini_api_key",
        together_api_key="test_together_api_key",
        debug=True,
    )


@pytest.fixture
def mock_quickbooks_client() -> Mock:
    """Create a mock QuickBooks client."""
    mock = Mock(spec=QuickBooksClient)
    mock.test_connection = AsyncMock(return_value={"CompanyName": "Test Company"})
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_oauth_config() -> QuickBooksOAuthConfig:
    """Create mock OAuth configuration."""
    return QuickBooksOAuthConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/callback",
    )


@pytest.fixture
def mock_token_info() -> QuickBooksTokenInfo:
    """Create mock token info."""
    now = datetime.now(UTC)
    return QuickBooksTokenInfo(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=100),
    )


@pytest.fixture
def mock_oauth_manager(
    mock_oauth_config: QuickBooksOAuthConfig,
    mock_token_info: QuickBooksTokenInfo,
) -> Mock:
    """Create mock OAuth manager."""
    mock = Mock(spec=QuickBooksOAuthManager)
    mock.config = mock_oauth_config
    mock.tokens = mock_token_info
    mock.has_valid_tokens = True
    mock.get_valid_access_token = AsyncMock(return_value=mock_token_info.access_token)
    mock.refresh_access_token = AsyncMock(return_value=mock_token_info)
    mock.add_token_update_callback = Mock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock()
    return mock


@pytest.fixture
def app(
    test_settings: Settings,
    mock_quickbooks_client: Mock,
    mock_oauth_manager: Mock,
) -> FastAPI:
    """Create test FastAPI app."""
    # Override settings
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings

    # Set mock services
    set_quickbooks_client(mock_quickbooks_client)
    set_oauth_manager(mock_oauth_manager)

    return app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_token_store(tmp_path: Path) -> TokenStore:
    """Create a mock token store with temporary file."""
    token_path = tmp_path / "test_tokens.json"
    return TokenStore(str(token_path))


@pytest.fixture
def sample_token_data() -> dict[str, Any]:
    """Sample token data for testing."""
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
        "x_refresh_token_expires_in": 8640000,
        "token_type": "bearer",
        "company_id": "test_company_123",
        "created_at": datetime.now(UTC).isoformat() + "Z",
    }
