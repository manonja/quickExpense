"""Admin endpoints for application management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException

if TYPE_CHECKING:
    from quickexpense.core.dependencies import RulesCacheDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/rules/status")
async def get_rules_cache_status(
    rules_cache: RulesCacheDep,
) -> dict[str, Any]:
    """Get business rules cache status.

    Returns:
        Cache status information including rule counts
    """
    try:
        return rules_cache.get_cache_status()
    except Exception as e:
        logger.error("Failed to get rules cache status: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache status: {e}"
        ) from e


@router.post("/rules/reload")
async def reload_business_rules(
    rules_cache: RulesCacheDep,
) -> dict[str, Any]:
    """Hot-reload business rules from configuration files.

    This endpoint allows administrators to reload business rules without
    restarting the application. Useful for updating rules in production.

    Returns:
        Reloaded rule counts and status
    """
    try:
        logger.info("Admin triggered hot-reload of business rules")
        rule_counts = rules_cache.reload_rules()

        return {
            "status": "success",
            "message": "Business rules reloaded successfully",
            "business_rules_count": rule_counts["business_rules_count"],
            "cra_rules_count": rule_counts["cra_rules_count"],
        }
    except Exception as e:
        logger.error("Failed to reload business rules: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to reload rules: {e}"
        ) from e
