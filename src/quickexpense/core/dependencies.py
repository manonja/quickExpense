"""Dependency injection for FastAPI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from quickexpense.core.config import Settings, get_settings
from quickexpense.services.quickbooks import QuickBooksService

if TYPE_CHECKING:
    from quickexpense.services.quickbooks import QuickBooksClient


# Global client instance that will be initialized on startup
_quickbooks_client: QuickBooksClient | None = None


def set_quickbooks_client(client: QuickBooksClient) -> None:
    """Set the global QuickBooks client instance."""
    global _quickbooks_client  # noqa: PLW0603
    _quickbooks_client = client


def get_quickbooks_client() -> QuickBooksClient:
    """Get the QuickBooks client instance."""
    if _quickbooks_client is None:
        msg = "QuickBooks client not initialized"
        raise RuntimeError(msg)
    return _quickbooks_client


def get_quickbooks_service(
    client: Annotated[QuickBooksClient, Depends(get_quickbooks_client)],
) -> QuickBooksService:
    """Get QuickBooks service instance."""
    return QuickBooksService(client)


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
QuickBooksServiceDep = Annotated[QuickBooksService, Depends(get_quickbooks_service)]
