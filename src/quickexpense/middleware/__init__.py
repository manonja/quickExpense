"""Middleware package for QuickExpense."""

from __future__ import annotations

__all__ = ["BasicAuthMiddleware"]

from .auth import BasicAuthMiddleware
