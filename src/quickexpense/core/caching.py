"""Async-compatible caching utilities for QuickBooks API."""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from cachetools import TTLCache

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")


def async_ttl_cache(
    maxsize: int = 256,
    ttl: float = 600,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Async-compatible TTL cache decorator.

    Args:
        maxsize: Maximum number of entries in cache
        ttl: Time-to-live in seconds

    Returns:
        Decorator function

    Example:
        >>> @async_ttl_cache(maxsize=100, ttl=300)
        >>> async def get_data(key: str) -> dict:
        >>>     return {"key": key}
    """
    cache: TTLCache[tuple[Any, ...], Any] = TTLCache(maxsize=maxsize, ttl=ttl)
    lock = asyncio.Lock()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            # Create cache key from args and kwargs
            # Skip 'self' argument for methods
            cache_args = args[1:] if args and hasattr(args[0], "__dict__") else args
            cache_key = (cache_args, tuple(sorted(kwargs.items())))

            # Check cache
            async with lock:
                if cache_key in cache:
                    logger.debug("Cache hit for %s", func.__name__)
                    return cache[cache_key]

            # Call function
            logger.debug("Cache miss for %s", func.__name__)
            result = await func(*args, **kwargs)

            # Store in cache
            async with lock:
                try:
                    cache[cache_key] = result
                except ValueError:
                    # Value too large for cache
                    logger.warning("Value too large for cache: %s", func.__name__)

            return result

        # Add cache inspection methods
        wrapper.cache_info = lambda: {  # type: ignore[attr-defined]
            "hits": cache.currsize,
            "misses": 0,  # TTLCache doesn't track misses
            "maxsize": maxsize,
            "currsize": cache.currsize,
            "ttl": ttl,
        }
        wrapper.cache_clear = lambda: cache.clear()  # type: ignore[attr-defined]

        return wrapper

    return decorator


def create_cache_key(*args: object, **kwargs: object) -> tuple[object, ...]:
    """Create a cache key from arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Tuple suitable for use as cache key
    """
    return (args, tuple(sorted(kwargs.items())))
