"""Cached QuickBooks service with TTL caching for API responses."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from quickexpense.core.caching import async_ttl_cache
from quickexpense.core.config import get_settings
from quickexpense.services.quickbooks import (
    AccountInfo,
    QuickBooksService,
    VendorSearchResult,
)

if TYPE_CHECKING:
    from quickexpense.services.quickbooks import QuickBooksClient

logger = logging.getLogger(__name__)


class CachedQuickBooksService(QuickBooksService):
    """QuickBooks service with caching for expensive API calls.

    This service wraps the base QuickBooksService and adds TTL caching
    to vendor and account lookups to reduce API calls and improve performance.
    """

    def __init__(self, client: QuickBooksClient) -> None:
        """Initialize the cached service.

        Args:
            client: QuickBooks client instance
        """
        super().__init__(client)
        settings = get_settings()
        self.cache_enabled = settings.enable_quickbooks_cache
        self.vendor_cache_ttl = settings.qb_vendor_cache_ttl
        self.account_cache_ttl = settings.qb_account_cache_ttl
        self.cache_max_size = settings.qb_cache_max_size

        # Apply caching decorators if enabled
        if self.cache_enabled:
            logger.info(
                "QuickBooks caching enabled: vendor_ttl=%ds, account_ttl=%ds",
                self.vendor_cache_ttl,
                self.account_cache_ttl,
            )
            self._cached_search_vendor = async_ttl_cache(
                maxsize=self.cache_max_size,
                ttl=self.vendor_cache_ttl,
            )(super().search_vendor)

            self._cached_get_expense_accounts = async_ttl_cache(
                maxsize=self.cache_max_size,
                ttl=self.account_cache_ttl,
            )(super().get_expense_accounts)

            self._cached_get_bank_accounts = async_ttl_cache(
                maxsize=self.cache_max_size,
                ttl=self.account_cache_ttl,
            )(super().get_bank_accounts)

            self._cached_get_credit_card_accounts = async_ttl_cache(
                maxsize=self.cache_max_size,
                ttl=self.account_cache_ttl,
            )(super().get_credit_card_accounts)
        else:
            logger.info("QuickBooks caching disabled")

    async def search_vendor(self, vendor_name: str) -> list[VendorSearchResult]:
        """Search for a vendor by name (cached).

        Args:
            vendor_name: Vendor name to search for

        Returns:
            List of matching vendors
        """
        if self.cache_enabled:
            return cast(
                list[VendorSearchResult],
                await self._cached_search_vendor(vendor_name),
            )
        return await super().search_vendor(vendor_name)

    async def get_expense_accounts(self) -> list[AccountInfo]:
        """Get all expense accounts (cached).

        Returns:
            List of expense accounts
        """
        if self.cache_enabled:
            return cast(
                list[AccountInfo],
                await self._cached_get_expense_accounts(),
            )
        return await super().get_expense_accounts()

    async def get_bank_accounts(self) -> list[AccountInfo]:
        """Get all bank accounts (cached).

        Returns:
            List of bank accounts
        """
        if self.cache_enabled:
            return cast(
                list[AccountInfo],
                await self._cached_get_bank_accounts(),
            )
        return await super().get_bank_accounts()

    async def get_credit_card_accounts(self) -> list[AccountInfo]:
        """Get all credit card accounts (cached).

        Returns:
            List of credit card accounts
        """
        if self.cache_enabled:
            return cast(
                list[AccountInfo],
                await self._cached_get_credit_card_accounts(),
            )
        return await super().get_credit_card_accounts()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache statistics
        """
        if not self.cache_enabled:
            return {"enabled": False}

        return {
            "enabled": True,
            "vendor_cache": self._cached_search_vendor.cache_info(),  # type: ignore[attr-defined]
            "expense_accounts_cache": self._cached_get_expense_accounts.cache_info(),  # type: ignore[attr-defined]
            "bank_accounts_cache": self._cached_get_bank_accounts.cache_info(),  # type: ignore[attr-defined]
            "credit_card_cache": self._cached_get_credit_card_accounts.cache_info(),  # type: ignore[attr-defined]
        }

    def clear_cache(self) -> None:
        """Clear all caches."""
        if not self.cache_enabled:
            return

        self._cached_search_vendor.cache_clear()  # type: ignore[attr-defined]
        self._cached_get_expense_accounts.cache_clear()  # type: ignore[attr-defined]
        self._cached_get_bank_accounts.cache_clear()  # type: ignore[attr-defined]
        self._cached_get_credit_card_accounts.cache_clear()  # type: ignore[attr-defined]
        logger.info("QuickBooks caches cleared")
