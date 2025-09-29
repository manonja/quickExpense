"""QuickExpense FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from quickexpense.api import health_router, main_router
from quickexpense.api.web_endpoints import router as web_api_router
from quickexpense.web.routes import router as web_ui_router
from quickexpense.core.config import Settings, get_settings
from quickexpense.core.dependencies import set_oauth_manager, set_quickbooks_client
from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
    QuickBooksTokenResponse,
)
from quickexpense.services.quickbooks import QuickBooksClient
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager
from quickexpense.services.token_store import TokenStore

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

    # Load tokens from JSON file
    token_store = TokenStore("data/tokens.json")
    token_data = token_store.load_tokens()

    initial_tokens = None
    company_id = None

    if token_data:
        try:
            # Convert stored tokens to QuickBooksTokenInfo
            token_response = QuickBooksTokenResponse(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data.get("expires_in", 3600),
                x_refresh_token_expires_in=token_data.get(
                    "x_refresh_token_expires_in", 8640000
                ),
                token_type=token_data.get("token_type", "bearer"),
            )
            initial_tokens = token_response.to_token_info()
            company_id = token_data.get("company_id")
            logger.info("Loaded OAuth tokens from tokens.json")
        except Exception as e:
            logger.error("Failed to load tokens from JSON: %s", e)
    else:
        logger.warning("No tokens found in tokens.json - OAuth setup required")

    oauth_manager = QuickBooksOAuthManager(
        config=oauth_config,
        initial_tokens=initial_tokens,
    )

    # Add callback to save tokens when they're updated
    def save_tokens_callback(tokens: QuickBooksTokenInfo) -> None:
        """Save updated tokens to JSON file."""
        try:
            token_data = {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_in": 3600,  # Default 1 hour
                "x_refresh_token_expires_in": 8640000,  # Default 100 days
                "token_type": "bearer",
                "company_id": company_id or settings.qb_company_id,
            }
            token_store.save_tokens(token_data)
            logger.info("Updated tokens saved to tokens.json")
        except Exception as e:
            logger.error("Failed to save updated tokens: %s", e)

    oauth_manager.add_token_update_callback(save_tokens_callback)
    set_oauth_manager(oauth_manager)

    # Initialize QuickBooks client with OAuth manager only if we have tokens
    async with oauth_manager:
        qb_client = None
        refresh_task = None

        if initial_tokens and not initial_tokens.refresh_token_expired:
            try:
                # Use company_id from tokens if available, otherwise from settings
                qb_client = QuickBooksClient(
                    base_url=settings.qb_base_url,
                    company_id=company_id or settings.qb_company_id,
                    oauth_manager=oauth_manager,
                )
                set_quickbooks_client(qb_client)
                logger.info("QuickBooks client initialized with OAuth manager")

                # Background task for token refresh
                if settings.qb_enable_background_refresh:
                    refresh_task = asyncio.create_task(
                        _background_token_refresh(oauth_manager, settings),
                    )
                    logger.info("Background token refresh task started")

                # Test connection on startup
                await qb_client.test_connection()
                logger.info("QuickBooks connection successful")

            except Exception as e:
                logger.warning("QuickBooks connection failed on startup: %s", e)
                # Don't fail startup - allow web UI to handle OAuth
                if qb_client:
                    await qb_client.close()
                    qb_client = None
        else:
            logger.info(
                "No valid tokens - QuickBooks client will be initialized after OAuth"
            )

        yield

        # Cleanup
        logger.info("Shutting down QuickExpense application...")
        if refresh_task:
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass
        if qb_client:
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

    # Mount static files
    from pathlib import Path

    static_dir = Path(__file__).parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include routers
    app.include_router(health_router)
    app.include_router(main_router)
    app.include_router(web_api_router)
    app.include_router(web_ui_router)

    # OAuth callback routes are handled by web_endpoints.py

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
