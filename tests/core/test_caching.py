"""Tests for async caching utilities."""

from __future__ import annotations

import asyncio

import pytest

from quickexpense.core.caching import async_ttl_cache, create_cache_key


@pytest.mark.asyncio
async def test_async_ttl_cache_basic() -> None:
    """Test basic async TTL cache functionality."""
    call_count = 0

    @async_ttl_cache(maxsize=10, ttl=10)
    async def get_value(key: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"value_{key}"

    # First call - cache miss
    result1 = await get_value("test")
    assert result1 == "value_test"
    assert call_count == 1

    # Second call with same args - cache hit
    result2 = await get_value("test")
    assert result2 == "value_test"
    assert call_count == 1  # Should not increment

    # Different args - cache miss
    result3 = await get_value("other")
    assert result3 == "value_other"
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_ttl_cache_expiry() -> None:
    """Test cache TTL expiration."""
    call_count = 0

    @async_ttl_cache(maxsize=10, ttl=0.1)  # 100ms TTL
    async def get_value(key: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"value_{key}"

    # First call
    result1 = await get_value("test")
    assert result1 == "value_test"
    assert call_count == 1

    # Wait for TTL to expire
    await asyncio.sleep(0.2)

    # Should call function again after TTL
    result2 = await get_value("test")
    assert result2 == "value_test"
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_ttl_cache_with_class_method() -> None:
    """Test caching with class methods."""

    class TestService:
        def __init__(self) -> None:
            self.call_count = 0

        @async_ttl_cache(maxsize=10, ttl=10)
        async def get_data(self, key: str) -> str:
            self.call_count += 1
            return f"data_{key}"

    service = TestService()

    # First call
    result1 = await service.get_data("test")
    assert result1 == "data_test"
    assert service.call_count == 1

    # Second call - should be cached
    result2 = await service.get_data("test")
    assert result2 == "data_test"
    assert service.call_count == 1


@pytest.mark.asyncio
async def test_async_ttl_cache_info() -> None:
    """Test cache info method."""

    @async_ttl_cache(maxsize=5, ttl=10)
    async def get_value(key: str) -> str:
        return f"value_{key}"

    # Make some calls
    await get_value("a")
    await get_value("b")
    await get_value("a")  # Cache hit

    # Check cache info
    info = get_value.cache_info()  # type: ignore[attr-defined]
    assert info["maxsize"] == 5
    assert info["ttl"] == 10
    assert info["currsize"] == 2  # 2 unique keys cached


@pytest.mark.asyncio
async def test_async_ttl_cache_clear() -> None:
    """Test cache clear method."""
    call_count = 0

    @async_ttl_cache(maxsize=10, ttl=10)
    async def get_value(key: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"value_{key}"

    # First call
    await get_value("test")
    assert call_count == 1

    # Second call - cached
    await get_value("test")
    assert call_count == 1

    # Clear cache
    get_value.cache_clear()  # type: ignore[attr-defined]

    # Should call function again after clear
    await get_value("test")
    assert call_count == 2


def test_create_cache_key() -> None:
    """Test cache key creation."""
    # With only positional args
    key1 = create_cache_key("a", "b", "c")
    assert key1 == (("a", "b", "c"), ())

    # With keyword args
    key2 = create_cache_key("a", b="test", c=123)
    assert key2 == (("a",), (("b", "test"), ("c", 123)))

    # Same args in different order should produce same key
    key3 = create_cache_key("a", c=123, b="test")
    assert key2 == key3


@pytest.mark.asyncio
async def test_async_ttl_cache_concurrent_calls() -> None:
    """Test cache behavior with concurrent calls."""
    call_count = 0

    @async_ttl_cache(maxsize=10, ttl=10)
    async def slow_function(key: str) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate slow operation
        return f"result_{key}"

    # Make concurrent calls with same key
    results = await asyncio.gather(
        slow_function("test"),
        slow_function("test"),
        slow_function("test"),
    )

    # All should return same result
    assert all(r == "result_test" for r in results)

    # Concurrent calls may all miss cache before first completes
    # This is expected behavior - after cache is populated, subsequent
    # calls will hit the cache
    assert call_count >= 1

    # Make sequential calls after cache is populated
    initial_count = call_count
    await slow_function("test")
    await slow_function("test")

    # These should be cache hits
    assert call_count == initial_count
