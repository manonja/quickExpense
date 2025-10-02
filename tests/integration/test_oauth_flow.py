"""Integration tests for OAuth flow with token storage."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from quickexpense.core.config import Settings
from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
    QuickBooksTokenResponse,
)
from quickexpense.services.quickbooks import QuickBooksClient
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from quickexpense.services.token_store import TokenStore


class TestOAuthFlowIntegration:
    """Test OAuth flow with token storage integration."""

    @pytest.fixture
    def token_file_path(self, tmp_path):
        """Create a temporary token file path."""
        return str(tmp_path / "tokens.json")

    @pytest.fixture
    def token_store(self, token_file_path):
        """Create token store instance."""
        return TokenStore(token_file_path)

    @pytest.fixture
    def oauth_config(self):
        """Create OAuth config."""
        return QuickBooksOAuthConfig(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:8000/callback",
        )

    @pytest.fixture
    def settings(self, token_file_path):
        """Create settings for testing."""
        return Settings(
            qb_base_url="https://sandbox-quickbooks.api.intuit.com",
            qb_client_id="test_client",
            qb_client_secret="test_secret",
            qb_company_id="",  # Will be loaded from tokens
            gemini_api_key="test_key",
            together_api_key="test_together_key",
        )

    @pytest.mark.asyncio
    async def test_initial_oauth_flow(self, oauth_config, token_store):
        """Test initial OAuth flow saves tokens to JSON."""
        # Mock HTTP client for token exchange
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
        }
        mock_http_client.post.return_value = mock_response

        # Create OAuth manager
        manager = QuickBooksOAuthManager(oauth_config)
        manager._http_client = mock_http_client

        # Add callback to save tokens
        saved_tokens = None

        def save_callback(tokens: QuickBooksTokenInfo) -> None:
            nonlocal saved_tokens
            saved_tokens = {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_in": 3600,
                "x_refresh_token_expires_in": 8640000,
                "token_type": "bearer",
                "company_id": "test_realm_123",
            }
            token_store.save_tokens(saved_tokens)

        manager.add_token_update_callback(save_callback)

        # Exchange code for tokens
        tokens = await manager.exchange_code_for_tokens(
            "test_auth_code",
            realm_id="test_realm_123",
        )

        # Verify tokens were obtained
        assert tokens.access_token == "new_access_token"
        assert tokens.refresh_token == "new_refresh_token"

        # Verify tokens were saved to file
        stored_tokens = token_store.load_tokens()
        assert stored_tokens is not None
        assert stored_tokens["access_token"] == "new_access_token"
        assert stored_tokens["refresh_token"] == "new_refresh_token"
        assert stored_tokens["company_id"] == "test_realm_123"

    @pytest.mark.asyncio
    async def test_token_refresh_updates_storage(self, oauth_config, token_store):
        """Test that token refresh updates the JSON storage."""
        # Save initial tokens
        initial_tokens = {
            "access_token": "old_access_token",
            "refresh_token": "old_refresh_token",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
            "company_id": "test_company",
        }
        token_store.save_tokens(initial_tokens)

        # Create token info from stored tokens
        token_response = QuickBooksTokenResponse(**initial_tokens)
        token_info = token_response.to_token_info()

        # Mock HTTP client for refresh
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_access_token",
            "refresh_token": "refreshed_refresh_token",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
        }
        mock_http_client.post.return_value = mock_response

        # Create OAuth manager with initial tokens
        manager = QuickBooksOAuthManager(oauth_config, initial_tokens=token_info)
        manager._http_client = mock_http_client

        # Add callback to save updated tokens
        def save_callback(tokens: QuickBooksTokenInfo) -> None:
            updated_data = {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_in": 3600,
                "x_refresh_token_expires_in": 8640000,
                "token_type": "bearer",
                "company_id": "test_company",
            }
            token_store.save_tokens(updated_data)

        manager.add_token_update_callback(save_callback)

        # Force token to be expired
        manager._tokens.access_token_expires_at = datetime.now(UTC) - timedelta(
            minutes=1
        )

        # Get valid access token (should trigger refresh)
        new_token = await manager.get_valid_access_token()
        assert new_token == "refreshed_access_token"

        # Verify tokens were updated in storage
        stored_tokens = token_store.load_tokens()
        assert stored_tokens["access_token"] == "refreshed_access_token"
        assert stored_tokens["refresh_token"] == "refreshed_refresh_token"

    @pytest.mark.asyncio
    async def test_app_startup_loads_tokens(self, token_store, settings):
        """Test that application startup correctly loads tokens from JSON."""
        # Save tokens to file
        test_tokens = {
            "access_token": "stored_access_token",
            "refresh_token": "stored_refresh_token",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
            "company_id": "stored_company_id",
            "created_at": datetime.now(UTC).isoformat() + "Z",
        }
        token_store.save_tokens(test_tokens)

        # Simulate app startup loading tokens
        loaded_data = token_store.load_tokens()
        assert loaded_data is not None

        # Convert to token info
        token_response = QuickBooksTokenResponse(
            access_token=loaded_data["access_token"],
            refresh_token=loaded_data["refresh_token"],
            expires_in=loaded_data.get("expires_in", 3600),
            x_refresh_token_expires_in=loaded_data.get(
                "x_refresh_token_expires_in", 8640000
            ),
            token_type=loaded_data.get("token_type", "bearer"),
        )
        token_info = token_response.to_token_info()

        # Verify tokens are loaded correctly
        assert token_info.access_token == "stored_access_token"
        assert token_info.refresh_token == "stored_refresh_token"

        # Company ID should be available
        assert loaded_data["company_id"] == "stored_company_id"

    @pytest.mark.asyncio
    async def test_quickbooks_client_with_token_storage(
        self, oauth_config, token_store
    ):
        """Test QuickBooks client integration with token storage."""
        # Save initial tokens
        initial_tokens = {
            "access_token": "client_access_token",
            "refresh_token": "client_refresh_token",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
            "company_id": "client_company_id",
        }
        token_store.save_tokens(initial_tokens)

        # Load tokens and create token info
        loaded = token_store.load_tokens()
        token_response = QuickBooksTokenResponse(**loaded)
        token_info = token_response.to_token_info()

        # Create OAuth manager
        manager = QuickBooksOAuthManager(oauth_config, initial_tokens=token_info)

        # Add token update callback
        def update_callback(tokens: QuickBooksTokenInfo):
            token_store.update_tokens(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
            )

        manager.add_token_update_callback(update_callback)

        # Create QuickBooks client
        client = QuickBooksClient(
            base_url="https://sandbox-quickbooks.api.intuit.com",
            company_id=loaded["company_id"],
            oauth_manager=manager,
        )

        # Verify client is configured correctly
        assert client.company_id == "client_company_id"
        assert client.oauth_manager is manager

    def test_missing_tokens_handled_gracefully(self, token_store):
        """Test that missing tokens.json is handled gracefully."""
        # No tokens file exists
        loaded = token_store.load_tokens()
        assert loaded is None

        # Application should handle this case
        # (would show message to run OAuth setup)

    def test_corrupted_tokens_handled(self, token_file_path):
        """Test that corrupted tokens.json is handled."""
        # Write corrupted JSON
        with open(token_file_path, "w") as f:
            f.write("{corrupted json")

        token_store = TokenStore(token_file_path)
        loaded = token_store.load_tokens()
        assert loaded is None  # Should return None, not crash
