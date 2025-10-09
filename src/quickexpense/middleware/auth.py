"""Authentication middleware for HuggingFace Space deployment."""

from __future__ import annotations

import base64
import logging
import secrets
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Authentication middleware for protecting public deployments.

    This middleware provides simple password protection for HuggingFace Space
    deployments while exempting essential paths like health checks and static files.
    """

    def __init__(
        self,
        app: ASGIApp,
        password: str,
        exempt_paths: list[str] | None = None,
    ) -> None:
        """Initialize the Basic Auth middleware.

        Args:
            app: The ASGI application to wrap
            password: The password required for authentication
            exempt_paths: List of path prefixes that don't require authentication
        """
        super().__init__(app)
        self.password = password
        self.exempt_paths = exempt_paths or [
            "/health",
            "/ready",
            "/static",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
        logger.info(
            "BasicAuthMiddleware initialized with %d exempt paths: %s",
            len(self.exempt_paths),
            ", ".join(self.exempt_paths),
        )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Check authentication before processing request.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The response from the application or a 401 Unauthorized response
        """
        # Skip authentication for exempt paths
        request_path = request.url.path
        if any(request_path.startswith(path) for path in self.exempt_paths):
            logger.debug("Skipping auth for exempt path: %s", request_path)
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Basic "):
            logger.warning(
                "Missing or invalid Authorization header from %s for path %s",
                self._get_client_ip(request),
                request_path,
            )
            return self._unauthorized_response()

        try:
            # Decode base64 credentials
            encoded_credentials = auth_header.split(" ", 1)[1]
            decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")

            # Parse username:password (we only care about password)
            if ":" not in decoded_credentials:
                logger.warning(
                    "Invalid credentials format from %s", self._get_client_ip(request)
                )
                return self._unauthorized_response()

            _, provided_password = decoded_credentials.split(":", 1)

            # Constant-time comparison to prevent timing attacks
            if not secrets.compare_digest(provided_password, self.password):
                logger.warning(
                    "Failed authentication attempt from %s for path %s",
                    self._get_client_ip(request),
                    request_path,
                )
                return self._unauthorized_response()

        except (ValueError, UnicodeDecodeError) as e:
            logger.warning(
                "Invalid authentication header format from %s: %s",
                self._get_client_ip(request),
                str(e),
            )
            return self._unauthorized_response()

        # Authentication successful - log for security monitoring
        logger.info(
            "Successful authentication from %s for path %s",
            self._get_client_ip(request),
            request_path,
        )
        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request, handling proxies.

        Args:
            request: The HTTP request

        Returns:
            The client IP address as a string
        """
        # Check for forwarded headers (common in deployed environments)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, first is the client
            return forwarded_for.split(",")[0].strip()

        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    def _unauthorized_response(self) -> JSONResponse:
        """Return 401 Unauthorized response with proper headers.

        Returns:
            JSONResponse with 401 status and WWW-Authenticate header
        """
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": "Authentication required",
                "message": "Please provide valid credentials to access this resource",
            },
            headers={
                "WWW-Authenticate": 'Basic realm="QuickExpense", charset="UTF-8"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
