"""LLM Provider abstraction layer for multi-provider support."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quickexpense.core.config import Settings

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers."""

    GEMINI = "gemini"
    TOGETHER = "together"
    AUTO = "auto"


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the provider with settings."""
        self.settings = settings

    @abstractmethod
    def get_autogen_config(self) -> dict[str, Any]:
        """Get autogen-compatible configuration for this provider."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available and configured."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of this provider."""


class TogetherAIProvider(BaseLLMProvider):
    """TogetherAI LLM provider implementation."""

    def get_autogen_config(self) -> dict[str, Any]:
        """Get autogen-compatible configuration for TogetherAI."""
        return {
            "config_list": [
                {
                    "model": self.settings.together_model,
                    "api_key": self.settings.together_api_key,
                    "api_type": "together",  # Critical for autogen
                    "max_tokens": self.settings.together_max_tokens,
                    "temperature": self.settings.together_temperature,
                }
            ],
            "cache_seed": None,  # Disable caching for consistency
        }

    def is_available(self) -> bool:
        """Check if TogetherAI is available."""
        return bool(self.settings.together_api_key)

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "together"


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider implementation."""

    def get_autogen_config(self) -> dict[str, Any]:
        """Get autogen-compatible configuration for Gemini."""
        return {
            "config_list": [
                {
                    "model": self.settings.gemini_model,
                    "api_key": self.settings.gemini_api_key,
                    "api_type": "google",
                    "temperature": 0.1,  # Low temperature for consistency
                    "max_tokens": 4096,
                }
            ],
            "cache_seed": None,
        }

    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return bool(self.settings.gemini_api_key)

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "gemini"


class LLMProviderFactory:
    """Factory for creating LLM providers with fallback support."""

    @staticmethod
    def create(  # noqa: C901
        settings: Settings, provider_override: str | None = None
    ) -> BaseLLMProvider:
        """Create an LLM provider based on settings or override.

        Args:
            settings: Application settings
            provider_override: Optional provider to use instead of default

        Returns:
            Configured LLM provider

        Raises:
            ValueError: If no provider is available
        """
        requested_provider = provider_override or settings.llm_provider

        # Handle specific provider requests
        if requested_provider == LLMProvider.TOGETHER.value:
            together_provider = TogetherAIProvider(settings)
            if together_provider.is_available():
                logger.info("Using TogetherAI provider")
                return together_provider
            if settings.llm_fallback_enabled:
                logger.warning("TogetherAI not available, falling back to Gemini")
                gemini_provider = GeminiProvider(settings)
                if gemini_provider.is_available():
                    return gemini_provider
            raise ValueError("TogetherAI not configured and no fallback available")

        if requested_provider == LLMProvider.GEMINI.value:
            gemini_provider = GeminiProvider(settings)
            if gemini_provider.is_available():
                logger.info("Using Gemini provider")
                return gemini_provider
            if settings.llm_fallback_enabled:
                logger.warning("Gemini not available, falling back to TogetherAI")
                together_provider = TogetherAIProvider(settings)
                if together_provider.is_available():
                    return together_provider
            raise ValueError("Gemini not configured and no fallback available")

        if requested_provider == LLMProvider.AUTO.value:
            # Try TogetherAI first (usually cheaper), then Gemini
            together_provider = TogetherAIProvider(settings)
            if together_provider.is_available():
                logger.info("Auto-selected TogetherAI provider")
                return together_provider

            gemini_provider = GeminiProvider(settings)
            if gemini_provider.is_available():
                logger.info("Auto-selected Gemini provider")
                return gemini_provider

            raise ValueError("No LLM providers configured")

        raise ValueError(f"Unknown provider: {requested_provider}")

    @staticmethod
    def get_model_for_agent(
        agent_type: str, provider: BaseLLMProvider, settings: Settings
    ) -> str:
        """Get optimal model for specific agent type.

        Args:
            agent_type: Type of agent (data_extraction, cra_rules, tax_calculator)
            provider: The LLM provider being used
            settings: Application settings

        Returns:
            Model name optimal for this agent type
        """
        if provider.provider_name == "together":
            # TogetherAI model recommendations per agent based on optimal performance
            model_map = {
                "data_extraction": "microsoft/phi-2",  # Efficient for data extraction
                "cra_rules": "meta-llama/Llama-3.3-70B-Instruct-Turbo",  # Legal reasoning
                "tax_calculator": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",  # Default
            }
            return model_map.get(agent_type, settings.together_model)
        # Use default Gemini model for all agents
        return settings.gemini_model
