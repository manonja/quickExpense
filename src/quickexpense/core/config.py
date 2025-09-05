"""Application configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # QuickBooks configuration
    qb_base_url: str = Field(
        default="https://sandbox-quickbooks.api.intuit.com",
        description="QuickBooks API base URL",
    )
    qb_client_id: str = Field(..., description="QuickBooks OAuth2 client ID")
    qb_client_secret: str = Field(..., description="QuickBooks OAuth2 client secret")
    qb_redirect_uri: str = Field(
        default="http://localhost:8000/callback",
        description="OAuth2 redirect URI",
    )
    # Company ID is now optional - will be loaded from tokens.json if available
    qb_company_id: str = Field(
        default="",
        description="QuickBooks company ID (optional - loaded from tokens.json)",
    )

    # OAuth configuration
    qb_oauth_environment: str = Field(
        default="sandbox",
        description="QuickBooks environment (sandbox/production)",
    )
    qb_token_refresh_buffer: int = Field(
        default=300,
        description="Seconds before token expiry to trigger refresh (5 min default)",
    )
    qb_max_refresh_attempts: int = Field(
        default=3,
        description="Maximum attempts to refresh token on failure",
    )
    qb_enable_background_refresh: bool = Field(
        default=True,
        description="Enable automatic background token refresh",
    )

    # Application settings
    app_name: str = Field(default="quickexpense", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # API settings
    api_prefix: str = Field(default="/api/v1", description="API route prefix")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Gemini AI configuration
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    gemini_model: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model to use",
    )
    gemini_timeout: int = Field(
        default=30,
        description="Timeout for Gemini API calls in seconds",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def quickbooks_api_url(self) -> str:
        """Construct the full QuickBooks API URL."""
        return f"{self.qb_base_url}/v3/company/{self.qb_company_id}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
