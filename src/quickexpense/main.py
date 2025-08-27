"""QuickExpense FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quickexpense.api import health_router, main_router
from quickexpense.core.config import get_settings
from quickexpense.core.dependencies import set_quickbooks_client
from quickexpense.services.quickbooks import QuickBooksClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI as FastAPIType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPIType) -> AsyncGenerator[None, None]:
    """Manage application lifecycle."""
    settings = get_settings()
    logger.info("Starting QuickExpense application...")

    # Initialize QuickBooks client
    qb_client = QuickBooksClient(
        base_url=settings.qb_base_url,
        company_id=settings.qb_company_id,
        access_token=settings.qb_access_token,
    )
    set_quickbooks_client(qb_client)

    logger.info("QuickBooks client initialized")

    try:
        # Test connection on startup
        await qb_client.test_connection()
        logger.info("QuickBooks connection successful")
    except Exception as e:
        logger.warning("QuickBooks connection failed on startup: %s", e)

    yield

    # Cleanup
    logger.info("Shutting down QuickExpense application...")
    await qb_client.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="QuickExpense",
        version=settings.app_version,
        description="A modern expense management API for QuickBooks",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(main_router)

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    log_level = settings.log_level.lower()

    uvicorn.run(
        "quickexpense.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=log_level,
    )
