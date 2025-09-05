"""QuickExpense FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quickexpense.api import health_router, main_router
from quickexpense.core.config import Settings, get_settings
from quickexpense.core.dependencies import set_oauth_manager, set_quickbooks_client
from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
)
from quickexpense.services.quickbooks import QuickBooksClient
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager

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

    # Initialize OAuth manager
    oauth_config = QuickBooksOAuthConfig(
        client_id=settings.qb_client_id,
        client_secret=settings.qb_client_secret,
        redirect_uri=settings.qb_redirect_uri,
        environment=settings.qb_oauth_environment,
        token_refresh_buffer=settings.qb_token_refresh_buffer,
        max_refresh_attempts=settings.qb_max_refresh_attempts,
    )

    # Create initial token info from settings
    from datetime import UTC, datetime, timedelta

    initial_tokens = QuickBooksTokenInfo(
        access_token=settings.qb_access_token,
        refresh_token=settings.qb_refresh_token,
        # Assume tokens were just obtained (will refresh if needed)
        access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        refresh_token_expires_at=datetime.now(UTC) + timedelta(days=100),
    )

    oauth_manager = QuickBooksOAuthManager(
        config=oauth_config,
        initial_tokens=initial_tokens,
    )
    set_oauth_manager(oauth_manager)

    # Initialize QuickBooks client with OAuth manager
    async with oauth_manager:
        qb_client = QuickBooksClient(
            base_url=settings.qb_base_url,
            company_id=settings.qb_company_id,
            oauth_manager=oauth_manager,
        )
        set_quickbooks_client(qb_client)

        logger.info("QuickBooks client initialized with OAuth manager")

        # Background task for token refresh
        refresh_task = None
        if settings.qb_enable_background_refresh:
            refresh_task = asyncio.create_task(
                _background_token_refresh(oauth_manager, settings),
            )
            logger.info("Background token refresh task started")

        try:
            # Test connection on startup
            await qb_client.test_connection()
            logger.info("QuickBooks connection successful")
        except Exception as e:
            logger.warning("QuickBooks connection failed on startup: %s", e)

        yield

        # Cleanup
        logger.info("Shutting down QuickExpense application...")
        if refresh_task:
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass
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


async def _background_token_refresh(
    oauth_manager: QuickBooksOAuthManager,
    settings: Settings,
) -> None:
    """Background task to refresh tokens proactively.

    Args:
        oauth_manager: OAuth manager instance
        settings: Application settings
    """
    while True:
        try:
            # Wait until we need to refresh (check every minute)
            await asyncio.sleep(60)

            if oauth_manager.tokens and oauth_manager.tokens.should_refresh(
                settings.qb_token_refresh_buffer,
            ):
                logger.info("Background token refresh triggered")
                await oauth_manager.refresh_access_token()

        except asyncio.CancelledError:
            logger.info("Background token refresh task cancelled")
            break
        except Exception:
            logger.exception("Error in background token refresh")
            # Continue running even if refresh fails
            await asyncio.sleep(60)
