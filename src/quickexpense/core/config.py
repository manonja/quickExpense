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
        default="http://localhost:8000/api/quickbooks/callback",
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

    # Enhanced logging configuration
    enable_ag2_logging: bool = Field(
        default=True, description="Enable AG2/AutoGen native logging"
    )
    enable_runtime_logging: bool = Field(
        default=True, description="Enable AG2 runtime database logging"
    )
    enable_conversation_logging: bool = Field(
        default=True, description="Enable conversation history logging"
    )
    enable_performance_monitoring: bool = Field(
        default=True, description="Enable performance monitoring and analytics"
    )
    ag2_trace_level: str = Field(default="DEBUG", description="AG2 trace logger level")
    ag2_event_level: str = Field(default="INFO", description="AG2 event logger level")
    logging_db_path: str = Field(
        default="data/agent_logs.db", description="Path to AG2 runtime logging database"
    )
    conversation_db_path: str = Field(
        default="data/conversation_history.db",
        description="Path to conversation history database",
    )
    log_retention_days: int = Field(
        default=2555,  # 7 years for CRA compliance
        description="Log retention period in days",
    )
    log_agent_reasoning: bool = Field(
        default=True, description="Log detailed agent reasoning and thought processes"
    )
    log_inter_agent_communication: bool = Field(
        default=True, description="Log communication between agents"
    )
    log_token_usage: bool = Field(
        default=True, description="Log LLM token usage and costs"
    )
    log_consensus_decisions: bool = Field(
        default=True, description="Log consensus decision making process"
    )
    performance_sampling_rate: float = Field(
        default=1.0, description="Sampling rate for performance metrics (0.0-1.0)"
    )

    # API settings
    api_prefix: str = Field(default="/api/v1", description="API route prefix")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # HuggingFace Space Protection
    hf_space_password: str = Field(
        default="",
        description="Password to protect HF Space deployment (leave empty to disable)",
    )
    enable_password_protection: bool = Field(
        default=False,
        description="Enable password protection middleware for public deployments",
    )

    # Gemini AI configuration (kept as fallback)
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model to use",
    )
    gemini_timeout: int = Field(
        default=30,
        description="Timeout for Gemini API calls in seconds",
    )

    # TogetherAI configuration
    together_api_key: str = Field(..., description="Together AI API key")
    together_model: str = Field(
        default="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        description="TogetherAI model to use",
    )
    together_max_tokens: int = Field(
        default=4096,
        description="Maximum tokens for TogetherAI responses",
    )
    together_temperature: float = Field(
        default=0.2,
        description="Temperature for TogetherAI (lower for consistency)",
    )

    # LLM Provider configuration
    llm_provider: str = Field(
        default="together",
        description="Primary LLM provider (together/gemini/auto)",
    )
    llm_fallback_enabled: bool = Field(
        default=True,
        description="Enable automatic fallback to secondary provider",
    )

    # Gemini rate limiting
    gemini_rpm_limit: int = Field(
        default=15,
        description="Gemini requests per minute limit (free tier: 15)",
    )
    gemini_rpd_limit: int = Field(
        default=1500,
        description="Gemini requests per day limit (free tier: 1500)",
    )

    # TogetherAI rate limiting
    together_rpm_limit: int = Field(
        default=60,
        description="TogetherAI requests per minute limit",
    )
    together_rpd_limit: int = Field(
        default=1500,
        description="TogetherAI requests per day limit",
    )

    # Rate limiter configuration
    rate_limiter_state_dir: str = Field(
        default="data",
        description="Directory for rate limiter state files",
    )

    # Caching configuration
    enable_business_rules_cache: bool = Field(
        default=True,
        description="Enable business rules caching at startup",
    )
    business_rules_config_path: str = Field(
        default="config/business_rules.json",
        description="Path to business rules JSON configuration",
    )
    cra_rules_csv_path: str = Field(
        default="config/cra_rules.csv",
        description="Path to CRA business rules CSV",
    )
    enable_quickbooks_cache: bool = Field(
        default=True,
        description="Enable QuickBooks API response caching",
    )
    qb_vendor_cache_ttl: int = Field(
        default=600,
        description="QuickBooks vendor cache TTL in seconds (10 minutes)",
    )
    qb_account_cache_ttl: int = Field(
        default=900,
        description="QuickBooks account cache TTL in seconds (15 minutes)",
    )
    qb_cache_max_size: int = Field(
        default=256,
        description="Maximum number of entries in QuickBooks caches",
    )

    model_config = SettingsConfigDict(
        env_file=[".env.example", ".env.local"],  # Local overrides example
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
