"""Dependency injection for FastAPI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from quickexpense.core.config import Settings, get_settings
from quickexpense.services.gemini import GeminiService
from quickexpense.services.quickbooks import QuickBooksService
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager

if TYPE_CHECKING:
    from quickexpense.services.quickbooks import QuickBooksClient


# Global instances that will be initialized on startup
_quickbooks_client: QuickBooksClient | None = None
_oauth_manager: QuickBooksOAuthManager | None = None


def set_quickbooks_client(client: QuickBooksClient | None) -> None:
    """Set the global QuickBooks client instance."""
    global _quickbooks_client  # noqa: PLW0603
    _quickbooks_client = client


def set_oauth_manager(manager: QuickBooksOAuthManager) -> None:
    """Set the global OAuth manager instance."""
    global _oauth_manager  # noqa: PLW0603
    _oauth_manager = manager


def get_quickbooks_client() -> QuickBooksClient | None:
    """Get the QuickBooks client instance."""
    return _quickbooks_client


def get_oauth_manager() -> QuickBooksOAuthManager:
    """Get the OAuth manager instance."""
    if _oauth_manager is None:
        msg = "OAuth manager not initialized"
        raise RuntimeError(msg)
    return _oauth_manager


def get_quickbooks_service() -> QuickBooksService | None:
    """Get QuickBooks service instance."""
    client = get_quickbooks_client()
    if client is None:
        return None
    return QuickBooksService(client)


def get_gemini_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GeminiService:
    """Get Gemini service instance."""
    return GeminiService(settings)


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
    QuickBooksService | None, Depends(get_quickbooks_service)
]
GeminiServiceDep = Annotated[GeminiService, Depends(get_gemini_service)]
OAuthManagerDep = Annotated[QuickBooksOAuthManager, Depends(get_oauth_manager)]
