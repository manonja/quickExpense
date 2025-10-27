"""QuickExpense API package."""

from .admin_endpoints import router as admin_router
from .health import router as health_router
from .monitoring_endpoints import router as monitoring_router
from .routes import router as main_router

__all__ = ["admin_router", "health_router", "main_router", "monitoring_router"]
