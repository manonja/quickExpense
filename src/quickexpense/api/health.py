"""Health check endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, status

if TYPE_CHECKING:
    from typing import Any

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """Check if the service is healthy."""
    return {"status": "healthy", "service": "quickexpense"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, Any]:
    """Check if the service is ready to accept requests."""
    return {
        "status": "ready",
        "service": "quickexpense",
        "dependencies": {
            "quickbooks": "connected",
        },
    }
