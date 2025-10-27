"""Rate limiter with state persistence for API quota management."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

from filelock import FileLock

if TYPE_CHECKING:
    from quickexpense.core.config import Settings

logger = logging.getLogger(__name__)

# Constants
RPM_WINDOW_SECONDS = 60  # 60 second window for requests per minute tracking


class RateLimiter:
    """Rate limiter with JSON state persistence and file locking.

    Tracks requests per minute (RPM) and requests per day (RPD) to prevent
    API quota exhaustion. State persists across application restarts.

    Features:
    - Separate RPM and RPD tracking
    - JSON state persistence with file locking for concurrent access
    - Timezone-aware daily reset (midnight Pacific Time)
    - Singleton pattern per provider
    """

    _instances: ClassVar[dict[str, RateLimiter]] = {}  # Singleton per provider

    def __init__(
        self,
        provider: str,
        rpm_limit: int,
        rpd_limit: int,
        state_dir: Path,
    ) -> None:
        """Initialize rate limiter for specific provider.

        Args:
            provider: Provider name (e.g., "gemini", "together")
            rpm_limit: Requests per minute limit (0 to disable)
            rpd_limit: Requests per day limit (0 to disable)
            state_dir: Directory for state file storage
        """
        self.provider = provider
        self.rpm_limit = rpm_limit
        self.rpd_limit = rpd_limit
        self.state_file = state_dir / f"rate_limiter_{provider}.json"
        self.lock_file = state_dir / f"rate_limiter_{provider}.lock"

        # Ensure state directory exists
        state_dir.mkdir(parents=True, exist_ok=True)

        # Load existing state or initialize
        self._load_state()

        logger.debug(
            "Rate limiter initialized for %s: RPM=%d, RPD=%d",
            provider,
            rpm_limit,
            rpd_limit,
        )

    @classmethod
    def get_instance(cls, provider: str, settings: Settings) -> RateLimiter:
        """Get or create singleton instance for provider.

        Args:
            provider: Provider name ("gemini" or "together")
            settings: Application settings

        Returns:
            RateLimiter instance for the provider

        Raises:
            ValueError: If provider is unknown
        """
        if provider not in cls._instances:
            # Determine limits based on provider
            if provider == "gemini":
                rpm = settings.gemini_rpm_limit
                rpd = settings.gemini_rpd_limit
            elif provider == "together":
                rpm = settings.together_rpm_limit
                rpd = settings.together_rpd_limit
            else:
                msg = f"Unknown provider: {provider}"
                raise ValueError(msg)

            state_dir = Path(settings.rate_limiter_state_dir)
            cls._instances[provider] = cls(provider, rpm, rpd, state_dir)

        return cls._instances[provider]

    def _load_state(self) -> None:
        """Load state from JSON file with file locking."""
        lock = FileLock(self.lock_file, timeout=10)

        try:
            with lock:
                if self.state_file.exists():
                    with self.state_file.open() as f:
                        data = json.load(f)
                    self.timestamps: list[float] = data.get("timestamps", [])
                    self.daily_count: int = data.get("daily_count", 0)
                    self.day_str: str = data.get("day_str", "")
                    logger.debug(
                        "Loaded rate limiter state for %s: daily_count=%d, day=%s",
                        self.provider,
                        self.daily_count,
                        self.day_str,
                    )
                else:
                    self.timestamps = []
                    self.daily_count = 0
                    self.day_str = ""
                    logger.debug(
                        "No existing state for %s, starting fresh", self.provider
                    )
        except OSError as e:
            logger.warning(
                "Failed to load rate limiter state for %s: %s", self.provider, e
            )
            self.timestamps = []
            self.daily_count = 0
            self.day_str = ""

    def _save_state(self) -> None:
        """Save state to JSON file with file locking."""
        lock = FileLock(self.lock_file, timeout=10)

        try:
            with lock:
                data = {
                    "timestamps": self.timestamps,
                    "daily_count": self.daily_count,
                    "day_str": self.day_str,
                }
                with self.state_file.open("w") as f:
                    json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(
                "Failed to save rate limiter state for %s: %s", self.provider, e
            )

    def _get_current_day_str(self) -> str:
        """Get current day string in Pacific Time.

        Returns:
            Date string in YYYY-MM-DD format
        """
        return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")

    def _reset_daily_counter(self) -> None:
        """Reset daily counter if new day detected (midnight Pacific Time)."""
        current_day = self._get_current_day_str()
        if current_day != self.day_str:
            logger.info(
                "Rate limiter %s: New day detected (%s -> %s), resetting daily count",
                self.provider,
                self.day_str,
                current_day,
            )
            self.daily_count = 0
            self.day_str = current_day

    def check_and_wait(self) -> None:
        """Check rate limits and wait if needed.

        This method:
        1. Resets daily counter if new day
        2. Checks daily limit (raises ValueError if exceeded)
        3. Checks RPM limit (waits if needed)
        4. Records new request
        5. Persists state

        Raises:
            ValueError: If daily quota exceeded
        """
        # Check if rate limiting is disabled
        if self.rpm_limit <= 0 and self.rpd_limit <= 0:
            logger.debug("Rate limiting disabled for %s", self.provider)
            return

        self._reset_daily_counter()

        # Check daily limit
        if self.rpd_limit > 0 and self.daily_count >= self.rpd_limit:
            msg = (
                f"Daily quota exceeded for {self.provider} "
                f"({self.daily_count}/{self.rpd_limit}). "
                f"Resets at midnight Pacific Time."
            )
            raise ValueError(msg)

        current_time = time.time()

        # Prune old timestamps (older than RPM_WINDOW_SECONDS for RPM window)
        self.timestamps = [
            ts for ts in self.timestamps if current_time - ts < RPM_WINDOW_SECONDS
        ]

        # Check RPM limit
        if self.rpm_limit > 0 and len(self.timestamps) >= self.rpm_limit:
            # Need to wait until oldest request expires
            oldest_timestamp = self.timestamps[0]
            wait_time = RPM_WINDOW_SECONDS - (current_time - oldest_timestamp)

            if wait_time > 0:
                logger.info(
                    "Rate limit reached for %s (%d/%d RPM), waiting %.1fs",
                    self.provider,
                    len(self.timestamps),
                    self.rpm_limit,
                    wait_time,
                )
                time.sleep(wait_time)
                current_time = time.time()

        # Record new request
        self.timestamps.append(current_time)
        self.daily_count += 1

        # Save state
        self._save_state()

        logger.debug(
            "Rate limiter %s: %d/%d RPM, %d/%d RPD",
            self.provider,
            len(self.timestamps),
            self.rpm_limit,
            self.daily_count,
            self.rpd_limit,
        )
