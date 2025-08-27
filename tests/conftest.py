"""Pytest configuration and fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from quickexpense.core.config import Settings, get_settings
from quickexpense.core.dependencies import set_quickbooks_client
from quickexpense.main import create_app
from quickexpense.services.quickbooks import QuickBooksClient

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        qb_base_url="https://sandbox-quickbooks.api.intuit.com",
        qb_client_id="test_client_id",
        qb_client_secret="test_client_secret",  # noqa: S106
        qb_redirect_uri="http://localhost:8000/callback",
        qb_company_id="test_company_id",
        qb_access_token="test_access_token",  # noqa: S106
        qb_refresh_token="test_refresh_token",  # noqa: S106
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
def app(test_settings: Settings, mock_quickbooks_client: Mock) -> FastAPI:
    """Create test FastAPI app."""
    # Override settings
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings

    # Set mock client
    set_quickbooks_client(mock_quickbooks_client)

    return app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client
