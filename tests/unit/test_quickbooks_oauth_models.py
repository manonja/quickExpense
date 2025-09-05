"""Tests for QuickBooks OAuth models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
    QuickBooksTokenResponse,
)


class TestQuickBooksTokenResponse:
    """Tests for QuickBooksTokenResponse model."""

    def test_create_valid_response(self) -> None:
        """Test creating a valid token response."""
        response = QuickBooksTokenResponse(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            x_refresh_token_expires_in=8640000,
        )
        assert response.access_token == "test_access_token"
        assert response.refresh_token == "test_refresh_token"
        assert response.token_type == "bearer"
        assert response.expires_in == 3600
        assert response.x_refresh_token_expires_in == 8640000

    def test_token_type_validation(self) -> None:
        """Test token type validation."""
        # Test valid bearer token (case insensitive)
        response = QuickBooksTokenResponse(
            access_token="token",
            refresh_token="refresh",
            token_type="Bearer",
            expires_in=3600,
            x_refresh_token_expires_in=8640000,
        )
        assert response.token_type == "bearer"

        # Test invalid token type
        with pytest.raises(ValidationError, match="Invalid token type"):
            QuickBooksTokenResponse(
                access_token="token",
                refresh_token="refresh",
                token_type="invalid",
                expires_in=3600,
                x_refresh_token_expires_in=8640000,
            )

    def test_to_token_info(self) -> None:
        """Test conversion to QuickBooksTokenInfo."""
        response = QuickBooksTokenResponse(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_in=3600,  # 1 hour
            x_refresh_token_expires_in=8640000,  # 100 days
        )

        # Convert to token info
        before_conversion = datetime.now(UTC)
        token_info = response.to_token_info()
        after_conversion = datetime.now(UTC)

        assert token_info.access_token == "test_access"
        assert token_info.refresh_token == "test_refresh"

        # Check access token expiry (should be ~1 hour from now)
        assert (
            before_conversion + timedelta(seconds=3600)
            <= token_info.access_token_expires_at
            <= after_conversion + timedelta(seconds=3600)
        )

        # Check refresh token expiry (should be ~100 days from now)
        assert (
            before_conversion + timedelta(seconds=8640000)
            <= token_info.refresh_token_expires_at
            <= after_conversion + timedelta(seconds=8640000)
        )


class TestQuickBooksTokenInfo:
    """Tests for QuickBooksTokenInfo model."""

    def test_create_valid_token_info(self) -> None:
        """Test creating valid token info."""
        now = datetime.now(UTC)
        token_info = QuickBooksTokenInfo(
            access_token="test_access",
            refresh_token="test_refresh",
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now + timedelta(days=100),
        )
        assert token_info.access_token == "test_access"
        assert token_info.refresh_token == "test_refresh"

    def test_access_token_expiry(self) -> None:
        """Test access token expiry checking."""
        now = datetime.now(UTC)

        # Token not expired
        token_info = QuickBooksTokenInfo(
            access_token="test",
            refresh_token="test",
            access_token_expires_at=now + timedelta(minutes=30),
            refresh_token_expires_at=now + timedelta(days=100),
        )
        assert not token_info.access_token_expired
        assert token_info.access_token_expires_in > 0

        # Token expired
        token_info_expired = QuickBooksTokenInfo(
            access_token="test",
            refresh_token="test",
            access_token_expires_at=now - timedelta(minutes=1),
            refresh_token_expires_at=now + timedelta(days=100),
        )
        assert token_info_expired.access_token_expired
        assert token_info_expired.access_token_expires_in == 0

    def test_refresh_token_expiry(self) -> None:
        """Test refresh token expiry checking."""
        now = datetime.now(UTC)

        # Token not expired
        token_info = QuickBooksTokenInfo(
            access_token="test",
            refresh_token="test",
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now + timedelta(days=50),
        )
        assert not token_info.refresh_token_expired
        assert token_info.refresh_token_expires_in > 0

        # Token expired
        token_info_expired = QuickBooksTokenInfo(
            access_token="test",
            refresh_token="test",
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now - timedelta(days=1),
        )
        assert token_info_expired.refresh_token_expired
        assert token_info_expired.refresh_token_expires_in == 0

    def test_should_refresh(self) -> None:
        """Test token refresh determination."""
        now = datetime.now(UTC)

        # Token expires in 10 minutes
        token_info = QuickBooksTokenInfo(
            access_token="test",
            refresh_token="test",
            access_token_expires_at=now + timedelta(minutes=10),
            refresh_token_expires_at=now + timedelta(days=100),
        )

        # With 5 minute buffer - should not refresh
        assert not token_info.should_refresh(buffer_seconds=300)

        # With 15 minute buffer - should refresh
        assert token_info.should_refresh(buffer_seconds=900)

        # Already expired - should refresh
        expired_token = QuickBooksTokenInfo(
            access_token="test",
            refresh_token="test",
            access_token_expires_at=now - timedelta(minutes=1),
            refresh_token_expires_at=now + timedelta(days=100),
        )
        assert expired_token.should_refresh(buffer_seconds=0)

    def test_model_dump_masked(self) -> None:
        """Test token masking for logging."""
        token_info = QuickBooksTokenInfo(
            access_token="very_long_access_token_string_here",
            refresh_token="very_long_refresh_token_string_here",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=100),
        )

        masked = token_info.model_dump_masked()
        assert masked["access_token"] == "very_long_...here"
        assert masked["refresh_token"] == "very_long_...here"
        assert "access_token_expires_at" in masked
        assert "refresh_token_expires_at" in masked

    def test_model_dump_masked_short_tokens(self) -> None:
        """Test token masking with short tokens."""
        token_info = QuickBooksTokenInfo(
            access_token="short",
            refresh_token="tiny",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=100),
        )

        masked = token_info.model_dump_masked()
        # Short tokens should still be masked (even if it looks odd)
        assert masked["access_token"] == "short...hort"
        assert masked["refresh_token"] == "tiny...tiny"


class TestQuickBooksOAuthConfig:
    """Tests for QuickBooksOAuthConfig model."""

    def test_create_valid_config(self) -> None:
        """Test creating valid OAuth config."""
        config = QuickBooksOAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8000/callback",
        )
        assert config.client_id == "test_client_id"
        assert config.client_secret == "test_client_secret"
        assert config.redirect_uri == "http://localhost:8000/callback"
        assert config.environment == "sandbox"
        assert config.token_refresh_buffer == 300
        assert config.max_refresh_attempts == 3

    def test_custom_config_values(self) -> None:
        """Test creating config with custom values."""
        config = QuickBooksOAuthConfig(
            client_id="prod_client",
            client_secret="prod_secret",
            redirect_uri="https://app.com/callback",
            environment="production",
            token_refresh_buffer=600,
            max_refresh_attempts=5,
        )
        assert config.environment == "production"
        assert config.token_refresh_buffer == 600
        assert config.max_refresh_attempts == 5

    def test_auth_base_url(self) -> None:
        """Test OAuth authorization URL generation."""
        config = QuickBooksOAuthConfig(
            client_id="test",
            client_secret="secret",
            redirect_uri="http://localhost",
        )
        assert config.auth_base_url == "https://appcenter.intuit.com/connect/oauth2"

    def test_token_url(self) -> None:
        """Test token endpoint URL."""
        config = QuickBooksOAuthConfig(
            client_id="test",
            client_secret="secret",
            redirect_uri="http://localhost",
        )
        expected = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        assert config.token_url == expected

    def test_revoke_url(self) -> None:
        """Test revoke endpoint URL."""
        config = QuickBooksOAuthConfig(
            client_id="test",
            client_secret="secret",
            redirect_uri="http://localhost",
        )
        expected = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
        assert config.revoke_url == expected


def test_full_oauth_flow_models() -> None:
    """Test the full OAuth model flow from response to token info."""
    # Simulate OAuth token response
    oauth_response_data: dict[str, Any] = {
        "access_token": "eyJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwiYWxnIjoiZGlyIn0...",
        "refresh_token": "AB11234567890abcdefghij",
        "token_type": "bearer",
        "expires_in": 3600,
        "x_refresh_token_expires_in": 8726400,
    }

    # Create response model
    response = QuickBooksTokenResponse(**oauth_response_data)
    assert response.token_type == "bearer"

    # Convert to token info
    token_info = response.to_token_info()
    assert token_info.access_token == oauth_response_data["access_token"]
    assert token_info.refresh_token == oauth_response_data["refresh_token"]

    # Check expiry calculations
    assert not token_info.access_token_expired
    assert not token_info.refresh_token_expired
    assert 3590 < token_info.access_token_expires_in < 3600
    assert token_info.refresh_token_expires_in > 8726390

    # Test refresh logic
    assert not token_info.should_refresh(buffer_seconds=300)  # 5 min buffer
    assert token_info.should_refresh(buffer_seconds=3700)  # 61 min buffer
