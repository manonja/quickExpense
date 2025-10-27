"""Tests for business rules cache service."""

from __future__ import annotations

import pytest

from quickexpense.core.config import Settings
from quickexpense.services.rules_cache import RulesCacheService


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        qb_client_id="test_client",
        qb_client_secret="test_secret",
        together_api_key="test_together_key",
        enable_business_rules_cache=True,
        business_rules_config_path="config/business_rules.json",
        cra_rules_csv_path="config/cra_rules.csv",
    )


@pytest.fixture
def disabled_cache_settings() -> Settings:
    """Create test settings with caching disabled."""
    return Settings(
        qb_client_id="test_client",
        qb_client_secret="test_secret",
        together_api_key="test_together_key",
        enable_business_rules_cache=False,
    )


def test_rules_cache_initialization(settings: Settings) -> None:
    """Test rules cache service initialization."""
    cache = RulesCacheService(settings)

    assert cache.settings == settings
    assert cache.business_rule_engine is None
    assert cache.cra_rules_service is None
    assert not cache.is_loaded


def test_rules_cache_load(settings: Settings) -> None:
    """Test loading rules into cache."""
    cache = RulesCacheService(settings)
    cache.load_rules()

    # Check that rules were loaded
    assert cache.is_loaded
    assert cache.business_rule_engine is not None
    assert cache.cra_rules_service is not None


def test_rules_cache_disabled(disabled_cache_settings: Settings) -> None:
    """Test that caching can be disabled."""
    cache = RulesCacheService(disabled_cache_settings)
    cache.load_rules()

    # Cache should not be loaded when disabled
    assert not cache.is_loaded


def test_rules_cache_get_status(settings: Settings) -> None:
    """Test getting cache status."""
    cache = RulesCacheService(settings)
    cache.load_rules()

    status = cache.get_cache_status()

    assert status["enabled"] is True
    assert status["loaded"] is True
    assert status["business_rules_loaded"] is True
    assert status["cra_rules_loaded"] is True
    assert status["business_rules_count"] > 0
    assert status["cra_rules_count"] > 0


def test_rules_cache_get_business_rule_engine(settings: Settings) -> None:
    """Test retrieving business rule engine from cache."""
    cache = RulesCacheService(settings)
    cache.load_rules()

    engine = cache.get_business_rule_engine()

    assert engine is not None
    assert engine.config is not None
    assert len(engine.config.rules) > 0


def test_rules_cache_get_cra_rules_service(settings: Settings) -> None:
    """Test retrieving CRA rules service from cache."""
    cache = RulesCacheService(settings)
    cache.load_rules()

    service = cache.get_cra_rules_service()

    assert service is not None
    assert len(service.rules) > 0


def test_rules_cache_lazy_load(settings: Settings) -> None:
    """Test lazy loading when accessing unloaded cache."""
    cache = RulesCacheService(settings)

    # Don't load explicitly - should lazy load on first access
    engine = cache.get_business_rule_engine()

    assert engine is not None
    assert cache.is_loaded


def test_rules_cache_reload(settings: Settings) -> None:
    """Test hot-reloading rules."""
    cache = RulesCacheService(settings)
    cache.load_rules()

    # Get initial counts
    initial_status = cache.get_cache_status()
    initial_business_count = initial_status["business_rules_count"]
    initial_cra_count = initial_status["cra_rules_count"]

    # Reload rules
    counts = cache.reload_rules()

    # Counts should be the same (assuming no file changes)
    assert counts["business_rules_count"] == initial_business_count
    assert counts["cra_rules_count"] == initial_cra_count


def test_rules_cache_get_engine_not_loaded_error() -> None:
    """Test error when accessing unloaded cache with invalid paths."""
    # Use invalid paths to force load failure
    settings = Settings(
        qb_client_id="test_client",
        qb_client_secret="test_secret",
        together_api_key="test_together_key",
        enable_business_rules_cache=True,
        business_rules_config_path="nonexistent/path.json",
        cra_rules_csv_path="nonexistent/path.csv",
    )

    cache = RulesCacheService(settings)

    # Should raise RuntimeError when lazy loading fails
    with pytest.raises(RuntimeError, match="Business rules engine not available"):
        cache.get_business_rule_engine()
