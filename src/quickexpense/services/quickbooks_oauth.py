"""QuickBooks OAuth token management service."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import TYPE_CHECKING, Any

import httpx

from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
    QuickBooksTokenResponse,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class QuickBooksOAuthError(Exception):
    """Exception for QuickBooks OAuth operations."""


class QuickBooksOAuthManager:
    """Manages QuickBooks OAuth token lifecycle."""

    def __init__(
        self,
        config: QuickBooksOAuthConfig,
        *,
        initial_tokens: QuickBooksTokenInfo | None = None,
    ) -> None:
        """Initialize OAuth manager.

        Args:
            config: OAuth configuration
            initial_tokens: Initial token info if available
        """
        self.config = config
        self._tokens = initial_tokens
        self._refresh_lock = asyncio.Lock()
        self._token_update_callbacks: list[Callable[[QuickBooksTokenInfo], None]] = []
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> QuickBooksOAuthManager:
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()

    @property
    def tokens(self) -> QuickBooksTokenInfo | None:
        """Get current token info."""
        return self._tokens

    @property
    def has_valid_tokens(self) -> bool:
        """Check if we have valid (non-expired) tokens."""
        return (
            self._tokens is not None
            and not self._tokens.access_token_expired
            and not self._tokens.refresh_token_expired
        )

    def add_token_update_callback(
        self,
        callback: Callable[[QuickBooksTokenInfo], None],
    ) -> None:
        """Add callback to be called when tokens are updated.

        Args:
            callback: Function to call with new token info
        """
        self._token_update_callbacks.append(callback)

    async def get_valid_access_token(self) -> str:
        """Get valid access token, refreshing if necessary.

        Returns:
            Valid access token

        Raises:
            QuickBooksOAuthError: If no tokens available or refresh fails
        """
        if not self._tokens:
            msg = "No tokens available - OAuth setup required"
            raise QuickBooksOAuthError(msg)

        if self._tokens.refresh_token_expired:
            msg = "Refresh token expired - new OAuth setup required"
            raise QuickBooksOAuthError(msg)

        # Check if we should refresh
        if self._tokens.should_refresh(self.config.token_refresh_buffer):
            await self.refresh_access_token()

        return self._tokens.access_token

    async def refresh_access_token(self) -> QuickBooksTokenInfo:
        """Refresh access token using refresh token.

        Returns:
            Updated token info

        Raises:
            QuickBooksOAuthError: If refresh fails
        """
        async with self._refresh_lock:  # Prevent concurrent refreshes
            if not self._tokens:
                msg = "No refresh token available"
                raise QuickBooksOAuthError(msg)

            if self._tokens.refresh_token_expired:
                msg = "Refresh token expired - new OAuth setup required"
                raise QuickBooksOAuthError(msg)

            # Check again if refresh needed (may have been refreshed already)
            if not self._tokens.should_refresh(self.config.token_refresh_buffer):
                return self._tokens

            logger.info("Refreshing QuickBooks access token")

            # Attempt refresh with retries
            last_error: Exception | None = None
            for attempt in range(self.config.max_refresh_attempts):
                try:
                    new_tokens = await self._perform_token_refresh(
                        self._tokens.refresh_token,
                    )
                    self._update_tokens(new_tokens)
                    logger.info("Successfully refreshed QuickBooks access token")
                    return self._tokens
                except Exception as e:  # noqa: BLE001
                    last_error = e
                    logger.warning(
                        "Token refresh attempt %d failed: %s",
                        attempt + 1,
                        e,
                    )
                    if attempt < self.config.max_refresh_attempts - 1:
                        await asyncio.sleep(2**attempt)  # Exponential backoff

            msg = (
                f"Failed to refresh token after "
                f"{self.config.max_refresh_attempts} attempts"
            )
            raise QuickBooksOAuthError(msg) from last_error

    async def _perform_token_refresh(self, refresh_token: str) -> QuickBooksTokenInfo:
        """Perform the actual token refresh HTTP request.

        Args:
            refresh_token: Current refresh token

        Returns:
            New token info

        Raises:
            QuickBooksOAuthError: If refresh request fails
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient()

        # Prepare Basic Auth header
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        auth_header = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header}",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            response = await self._http_client.post(
                self.config.token_url,
                headers=headers,
                data=data,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("Token refresh failed: %s", e.response.text)
            msg = f"Token refresh failed with status {e.response.status_code}"
            raise QuickBooksOAuthError(msg) from e
        except httpx.RequestError as e:
            msg = f"Token refresh request failed: {e}"
            raise QuickBooksOAuthError(msg) from e

        try:
            token_data = response.json()
            token_response = QuickBooksTokenResponse(**token_data)
            return token_response.to_token_info()
        except Exception as e:
            msg = f"Failed to parse token response: {e}"
            raise QuickBooksOAuthError(msg) from e

    def _update_tokens(self, new_tokens: QuickBooksTokenInfo) -> None:
        """Update stored tokens and notify callbacks.

        Args:
            new_tokens: New token information
        """
        self._tokens = new_tokens

        # Notify all callbacks
        for callback in self._token_update_callbacks:
            try:
                callback(new_tokens)
            except Exception:
                logger.exception("Error in token update callback")

    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
        *,
        realm_id: str | None = None,  # noqa: ARG002
    ) -> QuickBooksTokenInfo:
        """Exchange authorization code for tokens.

        Args:
            authorization_code: OAuth authorization code
            realm_id: QuickBooks company/realm ID

        Returns:
            Token information

        Raises:
            QuickBooksOAuthError: If exchange fails
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient()

        # Prepare Basic Auth header
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        auth_header = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header}",
        }

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.config.redirect_uri,
        }

        try:
            response = await self._http_client.post(
                self.config.token_url,
                headers=headers,
                data=data,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("Token exchange failed: %s", e.response.text)
            msg = f"Token exchange failed with status {e.response.status_code}"
            raise QuickBooksOAuthError(msg) from e
        except httpx.RequestError as e:
            msg = f"Token exchange request failed: {e}"
            raise QuickBooksOAuthError(msg) from e

        try:
            token_data = response.json()
            token_response = QuickBooksTokenResponse(**token_data)
            new_tokens = token_response.to_token_info()
            self._update_tokens(new_tokens)
            return new_tokens
        except Exception as e:
            msg = f"Failed to parse token response: {e}"
            raise QuickBooksOAuthError(msg) from e

    async def revoke_tokens(self) -> None:
        """Revoke current tokens.

        Raises:
            QuickBooksOAuthError: If revocation fails
        """
        if not self._tokens:
            return

        if not self._http_client:
            self._http_client = httpx.AsyncClient()

        # Use refresh token for revocation (revokes both tokens)
        token_to_revoke = self._tokens.refresh_token

        # Prepare Basic Auth header
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        auth_header = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_header}",
        }

        data = {"token": token_to_revoke}

        try:
            response = await self._http_client.post(
                self.config.revoke_url,
                headers=headers,
                json=data,
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info("Successfully revoked QuickBooks tokens")
            self._tokens = None
        except httpx.HTTPError as e:
            logger.error("Token revocation failed: %s", e)
            # Still clear tokens locally even if revocation fails
            self._tokens = None
            msg = f"Token revocation failed: {e}"
            raise QuickBooksOAuthError(msg) from e

    def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL
        """
        params: dict[str, Any] = {
            "client_id": self.config.client_id,
            "scope": "com.intuit.quickbooks.accounting",
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "state": state,
            "access_type": "offline",
        }

        from urllib.parse import urlencode

        return f"{self.config.auth_base_url}?{urlencode(params)}"
