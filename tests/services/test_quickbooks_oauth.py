"""Tests for QuickBooks OAuth service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
)
from quickexpense.services.quickbooks_oauth import (
    QuickBooksOAuthError,
    QuickBooksOAuthManager,
)


@pytest.fixture
def oauth_config() -> QuickBooksOAuthConfig:
    """Create test OAuth configuration."""
    return QuickBooksOAuthConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/callback",
        environment="sandbox",
        token_refresh_buffer=300,
        max_refresh_attempts=3,
    )


@pytest.fixture
def valid_token_info() -> QuickBooksTokenInfo:
    """Create valid token info for testing."""
    now = datetime.now(UTC)
    return QuickBooksTokenInfo(
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=100),
    )


@pytest.fixture
def expired_access_token_info() -> QuickBooksTokenInfo:
    """Create token info with expired access token."""
    now = datetime.now(UTC)
    return QuickBooksTokenInfo(
        access_token="expired_access_token",
        refresh_token="valid_refresh_token",
        access_token_expires_at=now - timedelta(minutes=5),
        refresh_token_expires_at=now + timedelta(days=100),
    )


@pytest.fixture
def expired_refresh_token_info() -> QuickBooksTokenInfo:
    """Create token info with expired refresh token."""
    now = datetime.now(UTC)
    return QuickBooksTokenInfo(
        access_token="access_token",
        refresh_token="expired_refresh_token",
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now - timedelta(days=1),
    )


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create mock HTTP client."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestQuickBooksOAuthManager:
    """Tests for QuickBooksOAuthManager."""

    def test_init_without_tokens(self, oauth_config: QuickBooksOAuthConfig) -> None:
        """Test initialization without initial tokens."""
        manager = QuickBooksOAuthManager(oauth_config)
        assert manager.config == oauth_config
        assert manager.tokens is None
        assert not manager.has_valid_tokens

    def test_init_with_tokens(
        self,
        oauth_config: QuickBooksOAuthConfig,
        valid_token_info: QuickBooksTokenInfo,
    ) -> None:
        """Test initialization with initial tokens."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=valid_token_info,
        )
        assert manager.tokens == valid_token_info
        assert manager.has_valid_tokens

    def test_has_valid_tokens_checks(
        self,
        oauth_config: QuickBooksOAuthConfig,
        valid_token_info: QuickBooksTokenInfo,
        expired_access_token_info: QuickBooksTokenInfo,
        expired_refresh_token_info: QuickBooksTokenInfo,
    ) -> None:
        """Test token validity checks."""
        # Valid tokens
        manager = QuickBooksOAuthManager(oauth_config, initial_tokens=valid_token_info)
        assert manager.has_valid_tokens

        # Expired access token (still valid for refresh)
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_access_token_info,
        )
        assert not manager.has_valid_tokens  # Access token expired

        # Expired refresh token
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_refresh_token_info,
        )
        assert not manager.has_valid_tokens

    def test_add_token_update_callback(
        self,
        oauth_config: QuickBooksOAuthConfig,
    ) -> None:
        """Test adding token update callbacks."""
        manager = QuickBooksOAuthManager(oauth_config)
        callback1 = MagicMock()
        callback2 = MagicMock()

        manager.add_token_update_callback(callback1)
        manager.add_token_update_callback(callback2)

        assert len(manager._token_update_callbacks) == 2

    @pytest.mark.asyncio
    async def test_get_valid_access_token_no_tokens(
        self,
        oauth_config: QuickBooksOAuthConfig,
    ) -> None:
        """Test getting access token when no tokens available."""
        manager = QuickBooksOAuthManager(oauth_config)

        with pytest.raises(
            QuickBooksOAuthError,
            match="No tokens available - OAuth setup required",
        ):
            await manager.get_valid_access_token()

    @pytest.mark.asyncio
    async def test_get_valid_access_token_expired_refresh(
        self,
        oauth_config: QuickBooksOAuthConfig,
        expired_refresh_token_info: QuickBooksTokenInfo,
    ) -> None:
        """Test getting access token when refresh token expired."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_refresh_token_info,
        )

        with pytest.raises(
            QuickBooksOAuthError,
            match="Refresh token expired - new OAuth setup required",
        ):
            await manager.get_valid_access_token()

    @pytest.mark.asyncio
    async def test_get_valid_access_token_no_refresh_needed(
        self,
        oauth_config: QuickBooksOAuthConfig,
        valid_token_info: QuickBooksTokenInfo,
    ) -> None:
        """Test getting valid access token when no refresh needed."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=valid_token_info,
        )

        token = await manager.get_valid_access_token()
        assert token == "valid_access_token"

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(
        self,
        oauth_config: QuickBooksOAuthConfig,
        expired_access_token_info: QuickBooksTokenInfo,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful token refresh."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_access_token_info,
        )
        manager._http_client = mock_http_client

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
        }
        mock_http_client.post.return_value = mock_response

        # Add callback to verify it's called
        callback = MagicMock()
        manager.add_token_update_callback(callback)

        # Perform refresh
        new_tokens = await manager.refresh_access_token()

        # Verify tokens updated
        assert new_tokens.access_token == "new_access_token"
        assert new_tokens.refresh_token == "new_refresh_token"
        assert manager.tokens == new_tokens

        # Verify callback called
        callback.assert_called_once_with(new_tokens)

        # Verify HTTP call
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == oauth_config.token_url
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["data"]["grant_type"] == "refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_access_token_concurrent_refresh_prevention(
        self,
        oauth_config: QuickBooksOAuthConfig,
        expired_access_token_info: QuickBooksTokenInfo,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test that concurrent refresh attempts are prevented."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_access_token_info,
        )
        manager._http_client = mock_http_client

        # Mock slow response
        async def slow_response(*args: Any, **kwargs: Any) -> MagicMock:
            await asyncio.sleep(0.1)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "token_type": "bearer",
                "expires_in": 3600,
                "x_refresh_token_expires_in": 8640000,
            }
            return mock_resp

        mock_http_client.post.side_effect = slow_response

        # Try concurrent refreshes
        results = await asyncio.gather(
            manager.refresh_access_token(),
            manager.refresh_access_token(),
            manager.refresh_access_token(),
        )

        # All should get same result
        assert all(r.access_token == "new_access_token" for r in results)

        # But only one HTTP call should be made
        assert mock_http_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_refresh_access_token_retry_logic(
        self,
        oauth_config: QuickBooksOAuthConfig,
        expired_access_token_info: QuickBooksTokenInfo,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test token refresh retry logic."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_access_token_info,
        )
        manager._http_client = mock_http_client

        # Mock failures then success
        mock_http_client.post.side_effect = [
            httpx.RequestError("Network error"),
            httpx.RequestError("Network error"),
            MagicMock(
                status_code=200,
                json=MagicMock(
                    return_value={
                        "access_token": "new_access_token",
                        "refresh_token": "new_refresh_token",
                        "token_type": "bearer",
                        "expires_in": 3600,
                        "x_refresh_token_expires_in": 8640000,
                    }
                ),
            ),
        ]

        # Should succeed after retries
        new_tokens = await manager.refresh_access_token()
        assert new_tokens.access_token == "new_access_token"
        assert mock_http_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_refresh_access_token_max_retries_exceeded(
        self,
        oauth_config: QuickBooksOAuthConfig,
        expired_access_token_info: QuickBooksTokenInfo,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test token refresh when max retries exceeded."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_access_token_info,
        )
        manager._http_client = mock_http_client

        # Mock all failures
        mock_http_client.post.side_effect = httpx.RequestError("Network error")

        with pytest.raises(
            QuickBooksOAuthError,
            match="Failed to refresh token after 3 attempts",
        ):
            await manager.refresh_access_token()

        assert mock_http_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_refresh_access_token_http_error(
        self,
        oauth_config: QuickBooksOAuthConfig,
        expired_access_token_info: QuickBooksTokenInfo,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test token refresh with HTTP error response."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expired_access_token_info,
        )
        manager._http_client = mock_http_client

        # Mock 401 response for all retries
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid refresh token"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )
        mock_http_client.post.return_value = mock_response

        # Since it will retry 3 times, it will fail with max attempts error
        with pytest.raises(
            QuickBooksOAuthError,
            match="Failed to refresh token after 3 attempts",
        ):
            await manager.refresh_access_token()

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(
        self,
        oauth_config: QuickBooksOAuthConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful authorization code exchange."""
        manager = QuickBooksOAuthManager(oauth_config)
        manager._http_client = mock_http_client

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
        }
        mock_http_client.post.return_value = mock_response

        # Exchange code
        tokens = await manager.exchange_code_for_tokens(
            "auth_code_123",
            realm_id="company_123",
        )

        # Verify tokens
        assert tokens.access_token == "new_access_token"
        assert manager.tokens == tokens

        # Verify HTTP call
        call_args = mock_http_client.post.call_args
        assert call_args[1]["data"]["grant_type"] == "authorization_code"
        assert call_args[1]["data"]["code"] == "auth_code_123"

    @pytest.mark.asyncio
    async def test_revoke_tokens_success(
        self,
        oauth_config: QuickBooksOAuthConfig,
        valid_token_info: QuickBooksTokenInfo,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test successful token revocation."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=valid_token_info,
        )
        manager._http_client = mock_http_client

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.post.return_value = mock_response

        # Revoke tokens
        await manager.revoke_tokens()

        # Verify tokens cleared
        assert manager.tokens is None

        # Verify HTTP call
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == oauth_config.revoke_url
        assert call_args[1]["json"]["token"] == "valid_refresh_token"

    @pytest.mark.asyncio
    async def test_revoke_tokens_failure_still_clears(
        self,
        oauth_config: QuickBooksOAuthConfig,
        valid_token_info: QuickBooksTokenInfo,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test token revocation failure still clears local tokens."""
        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=valid_token_info,
        )
        manager._http_client = mock_http_client

        # Mock failed response
        mock_http_client.post.side_effect = httpx.RequestError("Network error")

        # Should raise error but still clear tokens
        with pytest.raises(
            QuickBooksOAuthError,
            match="Token revocation failed",
        ):
            await manager.revoke_tokens()

        assert manager.tokens is None

    def test_get_authorization_url(
        self,
        oauth_config: QuickBooksOAuthConfig,
    ) -> None:
        """Test OAuth authorization URL generation."""
        manager = QuickBooksOAuthManager(oauth_config)

        url = manager.get_authorization_url("test_state_123")

        # Parse URL
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "appcenter.intuit.com"
        assert parsed.path == "/connect/oauth2"
        assert params["client_id"][0] == "test_client_id"
        assert params["state"][0] == "test_state_123"
        assert params["response_type"][0] == "code"
        assert params["scope"][0] == "com.intuit.quickbooks.accounting"
        assert params["redirect_uri"][0] == "http://localhost:8000/callback"
        assert params["access_type"][0] == "offline"

    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        oauth_config: QuickBooksOAuthConfig,
    ) -> None:
        """Test async context manager functionality."""
        async with QuickBooksOAuthManager(oauth_config) as manager:
            assert manager._http_client is not None

        # Client should be closed after exiting context
        # (Can't directly test closure, but no errors should occur)

    def test_callback_error_handling(
        self,
        oauth_config: QuickBooksOAuthConfig,
        valid_token_info: QuickBooksTokenInfo,
    ) -> None:
        """Test error handling in token update callbacks."""
        manager = QuickBooksOAuthManager(oauth_config)

        # Add callbacks, one that raises
        good_callback = MagicMock()
        bad_callback = MagicMock(side_effect=Exception("Callback error"))

        manager.add_token_update_callback(bad_callback)
        manager.add_token_update_callback(good_callback)

        # Update tokens - should not raise despite bad callback
        manager._update_tokens(valid_token_info)

        # Good callback should still be called
        good_callback.assert_called_once_with(valid_token_info)

    @pytest.mark.asyncio
    async def test_get_valid_access_token_with_refresh(
        self,
        oauth_config: QuickBooksOAuthConfig,
        mock_http_client: AsyncMock,
    ) -> None:
        """Test getting access token that triggers refresh."""
        # Token that needs refresh
        now = datetime.now(UTC)
        expiring_token = QuickBooksTokenInfo(
            access_token="old_access_token",
            refresh_token="valid_refresh_token",
            access_token_expires_at=now + timedelta(minutes=3),  # Within buffer
            refresh_token_expires_at=now + timedelta(days=100),
        )

        manager = QuickBooksOAuthManager(
            oauth_config,
            initial_tokens=expiring_token,
        )
        manager._http_client = mock_http_client

        # Mock refresh response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
        }
        mock_http_client.post.return_value = mock_response

        # Get token - should trigger refresh
        token = await manager.get_valid_access_token()
        assert token == "new_access_token"
        assert mock_http_client.post.called
