"""QuickBooks OAuth models for token management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QuickBooksTokenResponse(BaseModel):
    """Response model for QuickBooks OAuth token endpoint."""

    access_token: str = Field(..., description="Bearer token for API access")
    refresh_token: str = Field(..., description="Token for refreshing access")
    token_type: str = Field(default="bearer", description="Type of token")
    expires_in: int = Field(..., description="Access token expiry in seconds")
    x_refresh_token_expires_in: int = Field(
        ...,
        description="Refresh token expiry in seconds",
        alias="x_refresh_token_expires_in",
    )

    @field_validator("token_type")
    @classmethod
    def validate_token_type(cls, v: str) -> str:
        """Ensure token type is bearer."""
        if v.lower() != "bearer":
            msg = f"Invalid token type: {v}"
            raise ValueError(msg)
        return v.lower()

    def to_token_info(self) -> QuickBooksTokenInfo:
        """Convert response to token info with calculated expiry times."""
        now = datetime.now(UTC)
        return QuickBooksTokenInfo(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            access_token_expires_at=now + timedelta(seconds=self.expires_in),
            refresh_token_expires_at=now
            + timedelta(seconds=self.x_refresh_token_expires_in),
        )


class QuickBooksTokenInfo(BaseModel):
    """Token information with expiry tracking."""

    access_token: str = Field(..., description="Current access token")
    refresh_token: str = Field(..., description="Current refresh token")
    access_token_expires_at: datetime = Field(
        ...,
        description="UTC timestamp when access token expires",
    )
    refresh_token_expires_at: datetime = Field(
        ...,
        description="UTC timestamp when refresh token expires",
    )

    @property
    def access_token_expired(self) -> bool:
        """Check if access token is expired."""
        return datetime.now(UTC) >= self.access_token_expires_at

    @property
    def refresh_token_expired(self) -> bool:
        """Check if refresh token is expired."""
        return datetime.now(UTC) >= self.refresh_token_expires_at

    @property
    def access_token_expires_in(self) -> float:
        """Get seconds until access token expires."""
        delta = self.access_token_expires_at - datetime.now(UTC)
        return max(0, delta.total_seconds())

    @property
    def refresh_token_expires_in(self) -> float:
        """Get seconds until refresh token expires."""
        delta = self.refresh_token_expires_at - datetime.now(UTC)
        return max(0, delta.total_seconds())

    def should_refresh(self, buffer_seconds: int = 300) -> bool:
        """Check if token should be refreshed (with buffer before expiry).

        Args:
            buffer_seconds: Refresh if less than this many seconds until expiry

        Returns:
            True if token should be refreshed
        """
        return self.access_token_expires_in <= buffer_seconds

    def model_dump_masked(self) -> dict[str, Any]:
        """Return model dict with masked tokens for logging."""
        data = self.model_dump()
        if self.access_token:
            data["access_token"] = (
                f"{self.access_token[:10]}...{self.access_token[-4:]}"
            )
        if self.refresh_token:
            data["refresh_token"] = (
                f"{self.refresh_token[:10]}...{self.refresh_token[-4:]}"
            )
        return data


class QuickBooksOAuthConfig(BaseModel):
    """Configuration for QuickBooks OAuth."""

    client_id: str = Field(..., description="QuickBooks OAuth client ID")
    client_secret: str = Field(..., description="QuickBooks OAuth client secret")
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    environment: str = Field(
        default="sandbox",
        description="QuickBooks environment (sandbox/production)",
    )
    token_refresh_buffer: int = Field(
        default=300,
        description="Seconds before expiry to refresh token",
    )
    max_refresh_attempts: int = Field(
        default=3,
        description="Maximum token refresh retry attempts",
    )

    @property
    def auth_base_url(self) -> str:
        """Get OAuth authorization base URL."""
        return "https://appcenter.intuit.com/connect/oauth2"

    @property
    def token_url(self) -> str:
        """Get OAuth token endpoint URL."""
        return "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    @property
    def revoke_url(self) -> str:
        """Get OAuth token revocation endpoint URL."""
        return "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
