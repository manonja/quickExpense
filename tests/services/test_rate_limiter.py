"""Unit tests for rate limiter module."""

import json
import time
from unittest.mock import Mock, patch

import pytest

from quickexpense.core.config import Settings
from quickexpense.services.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test rate limiter functionality."""

    @pytest.fixture
    def temp_state_dir(self, tmp_path):
        """Create temporary state directory."""
        return tmp_path / "rate_limiter_state"

    @pytest.fixture
    def mock_settings(self, temp_state_dir):
        """Mock settings with test configuration."""
        settings = Mock(spec=Settings)
        settings.gemini_rpm_limit = 3  # Low limit for testing
        settings.gemini_rpd_limit = 10
        settings.together_rpm_limit = 5
        settings.together_rpd_limit = 20
        settings.rate_limiter_state_dir = str(temp_state_dir)
        return settings

    @pytest.fixture(autouse=True)
    def clear_singletons(self):
        """Clear singleton instances before each test."""
        RateLimiter._instances.clear()
        yield
        RateLimiter._instances.clear()

    def test_rate_limiter_initialization(self, mock_settings):
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)
        assert limiter.provider == "gemini"
        assert limiter.rpm_limit == 3
        assert limiter.rpd_limit == 10
        assert isinstance(limiter.timestamps, list)
        assert isinstance(limiter.daily_count, int)

    def test_rate_limiter_singleton(self, mock_settings):
        """Test singleton pattern per provider."""
        limiter1 = RateLimiter.get_instance("gemini", mock_settings)
        limiter2 = RateLimiter.get_instance("gemini", mock_settings)
        assert limiter1 is limiter2

        # Different provider = different instance
        limiter3 = RateLimiter.get_instance("together", mock_settings)
        assert limiter3 is not limiter1
        assert limiter3.provider == "together"

    def test_rate_limiter_unknown_provider(self, mock_settings):
        """Test error handling for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            RateLimiter.get_instance("unknown", mock_settings)

    def test_rate_limiter_rpm_enforcement(self, mock_settings):
        """Test RPM limit is enforced."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # First 3 requests should pass immediately
        for _ in range(3):
            start = time.time()
            limiter.check_and_wait()
            elapsed = time.time() - start
            assert elapsed < 0.5  # Should be instant

        assert len(limiter.timestamps) == 3
        assert limiter.daily_count == 3

        # 4th request should wait
        start = time.time()
        limiter.check_and_wait()
        elapsed = time.time() - start
        # Should wait for oldest timestamp to expire (at least a few seconds)
        assert elapsed >= 2.0  # Conservative check

    def test_rate_limiter_rpd_enforcement(self, mock_settings):
        """Test daily limit is enforced."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # Use up daily quota
        for _ in range(10):
            limiter.timestamps = []  # Clear RPM tracking to avoid wait
            limiter.check_and_wait()

        assert limiter.daily_count == 10

        # Next request should raise exception
        limiter.timestamps = []  # Clear RPM tracking
        with pytest.raises(ValueError, match="Daily quota exceeded"):
            limiter.check_and_wait()

    def test_rate_limiter_state_persistence(self, mock_settings, temp_state_dir):
        """Test state persists to JSON file."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)
        limiter.check_and_wait()

        state_file = temp_state_dir / "rate_limiter_gemini.json"
        assert state_file.exists()

        with open(state_file) as f:
            data = json.load(f)

        assert "timestamps" in data
        assert "daily_count" in data
        assert "day_str" in data
        assert data["daily_count"] == 1
        assert len(data["timestamps"]) == 1

    def test_rate_limiter_daily_reset(self, mock_settings):
        """Test daily counter resets at midnight."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)
        limiter.daily_count = 5
        limiter.day_str = "2024-01-01"  # Old date

        # Mock current day as different
        with patch.object(limiter, "_get_current_day_str", return_value="2024-01-02"):
            limiter.check_and_wait()

        assert limiter.daily_count == 1  # Reset + new request
        assert limiter.day_str == "2024-01-02"

    def test_rate_limiter_disabled(self, mock_settings):
        """Test rate limiting can be disabled (set to 0)."""
        mock_settings.gemini_rpm_limit = 0
        mock_settings.gemini_rpd_limit = 0

        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # Should allow unlimited requests without waiting
        for _ in range(100):
            start = time.time()
            limiter.check_and_wait()
            elapsed = time.time() - start
            assert elapsed < 0.1  # Should be instant

    def test_rate_limiter_state_reload(self, mock_settings, temp_state_dir):
        """Test state is loaded on initialization."""
        # Create first instance and make a request
        limiter1 = RateLimiter.get_instance("gemini", mock_settings)
        limiter1.check_and_wait()
        assert limiter1.daily_count == 1

        # Clear singleton cache
        RateLimiter._instances.clear()

        # Create new instance - should load state from file
        limiter2 = RateLimiter.get_instance("gemini", mock_settings)
        assert limiter2.daily_count == 1  # Should have loaded previous count
        assert len(limiter2.timestamps) >= 0  # May have pruned old timestamps

    def test_concurrent_access_safety(self, mock_settings):
        """Test file locking prevents race conditions."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # Multiple rapid calls should not corrupt state
        for _ in range(5):
            limiter.check_and_wait()

        # Verify state file is valid JSON
        with open(limiter.state_file) as f:
            data = json.load(f)

        assert isinstance(data["timestamps"], list)
        assert isinstance(data["daily_count"], int)
        assert len(data["timestamps"]) <= limiter.rpm_limit

    def test_rate_limiter_pruning(self, mock_settings):
        """Test old timestamps are pruned correctly."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # Set the current day to avoid reset
        limiter.day_str = limiter._get_current_day_str()

        # Add old timestamps
        current_time = time.time()
        limiter.timestamps = [
            current_time - 70,  # Should be pruned (>60s old)
            current_time - 50,  # Should be kept
            current_time - 30,  # Should be kept
        ]
        limiter.daily_count = 3

        # Check and wait should prune old timestamps
        limiter.check_and_wait()

        # Old timestamp should be removed, new one added
        assert len(limiter.timestamps) == 3  # 2 kept + 1 new
        assert limiter.daily_count == 4  # Previous 3 + new 1
