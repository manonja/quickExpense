"""Dependency injection for FastAPI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from quickexpense.core.config import Settings, get_settings
from quickexpense.services.agents import (
    AgentOrchestrator,
    CRArulesAgent,
    DataExtractionAgent,
)
from quickexpense.services.business_rules import BusinessRuleEngine
from quickexpense.services.gemini import GeminiService
from quickexpense.services.quickbooks_cached import CachedQuickBooksService
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from quickexpense.services.rules_cache import RulesCacheService

if TYPE_CHECKING:
    from quickexpense.services.quickbooks import QuickBooksClient


# Global instances that will be initialized on startup
_quickbooks_client: QuickBooksClient | None = None
_oauth_manager: QuickBooksOAuthManager | None = None
_business_rules_engine: BusinessRuleEngine | None = None
_rules_cache: RulesCacheService | None = None


def set_quickbooks_client(client: QuickBooksClient | None) -> None:
    """Set the global QuickBooks client instance."""
    global _quickbooks_client  # noqa: PLW0603
    _quickbooks_client = client


def set_oauth_manager(manager: QuickBooksOAuthManager) -> None:
    """Set the global OAuth manager instance."""
    global _oauth_manager  # noqa: PLW0603
    _oauth_manager = manager


def set_business_rules_engine(engine: BusinessRuleEngine) -> None:
    """Set the global business rules engine instance."""
    global _business_rules_engine  # noqa: PLW0603
    _business_rules_engine = engine


def set_rules_cache(cache: RulesCacheService) -> None:
    """Set the global rules cache instance."""
    global _rules_cache  # noqa: PLW0603
    _rules_cache = cache


def get_quickbooks_client() -> QuickBooksClient | None:
    """Get the QuickBooks client instance."""
    return _quickbooks_client


def get_oauth_manager() -> QuickBooksOAuthManager:
    """Get the OAuth manager instance."""
    if _oauth_manager is None:
        msg = "OAuth manager not initialized"
        raise RuntimeError(msg)
    return _oauth_manager


def get_business_rules_engine() -> BusinessRuleEngine:
    """Get the business rules engine instance."""
    if _business_rules_engine is None:
        msg = "Business rules engine not initialized"
        raise RuntimeError(msg)
    return _business_rules_engine


def get_rules_cache() -> RulesCacheService:
    """Get the rules cache instance."""
    if _rules_cache is None:
        msg = "Rules cache not initialized"
        raise RuntimeError(msg)
    return _rules_cache


def get_quickbooks_service() -> CachedQuickBooksService | None:
    """Get QuickBooks service instance with caching."""
    client = get_quickbooks_client()
    if client is None:
        return None
    return CachedQuickBooksService(client)


def get_gemini_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GeminiService:
    """Get Gemini service instance."""
    return GeminiService(settings)


def get_multi_agent_orchestrator(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentOrchestrator:
    """Get multi-agent orchestrator instance (2-agent system)."""
    # Create the two specialized agents (tax calculations integrated in CRArulesAgent)
    data_extraction_agent = DataExtractionAgent(settings=settings)
    cra_rules_agent = CRArulesAgent(settings=settings)

    # Create and return orchestrator
    return AgentOrchestrator(
        data_extraction_agent=data_extraction_agent,
        cra_rules_agent=cra_rules_agent,
        consensus_threshold=0.75,
    )


async def initialize_quickbooks_client_after_oauth(company_id: str) -> None:
    """Initialize QuickBooks client after successful OAuth."""
    from quickexpense.core.config import get_settings
    from quickexpense.services.quickbooks import QuickBooksClient

    settings = get_settings()
    oauth_manager = get_oauth_manager()

    # Create new QuickBooks client with the company ID from OAuth
    qb_client = QuickBooksClient(
        base_url=settings.qb_base_url,
        company_id=company_id,
        oauth_manager=oauth_manager,
    )

    set_quickbooks_client(qb_client)


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
QuickBooksServiceDep = Annotated[
    CachedQuickBooksService | None, Depends(get_quickbooks_service)
]
GeminiServiceDep = Annotated[GeminiService, Depends(get_gemini_service)]
MultiAgentOrchestratorDep = Annotated[
    AgentOrchestrator, Depends(get_multi_agent_orchestrator)
]
OAuthManagerDep = Annotated[QuickBooksOAuthManager, Depends(get_oauth_manager)]
BusinessRulesEngineDep = Annotated[
    BusinessRuleEngine, Depends(get_business_rules_engine)
]
RulesCacheDep = Annotated[RulesCacheService, Depends(get_rules_cache)]
