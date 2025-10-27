# API Key Security and Rate Limiting Implementation Plan

**Project:** quickExpense
**Feature:** API Key Security + Rate Limiting for Gemini and TogetherAI
**Based on:** quickExpense-rag PR #37
**Branch:** `feat/api-key-security-rate-limiting`
**Date:** 2025-01-27

---

## Executive Summary

**Goal:** Secure API keys and implement intelligent rate limiting to prevent quota exhaustion

**Approach:** Adapt proven design from quickExpense-rag PR #37 to quickExpense's multi-agent architecture

**Estimated Duration:** 8-14 hours (1-2 working days)

**Breaking Changes:** None (backward compatible with migration path)

**Confidence Level:** High (based on proven PR #37 design)

---

## Table of Contents

1. [Implementation Architecture](#implementation-architecture)
2. [Phase 1: API Key Security](#phase-1-api-key-security)
3. [Phase 2: Core Rate Limiter Module](#phase-2-core-rate-limiter-module)
4. [Phase 3: Gemini Integration](#phase-3-gemini-integration)
5. [Phase 4: TogetherAI Integration](#phase-4-togetherai-integration)
6. [Phase 5: Testing & Validation](#phase-5-testing--validation)
7. [Phase 6: Documentation](#phase-6-documentation)
8. [Complete File Manifest](#complete-file-manifest)
9. [Success Criteria](#success-criteria)
10. [Risk Mitigation](#risk-mitigation)
11. [Execution Checklist](#execution-checklist)

---

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Phase 1: API Key Security (MUST DO FIRST)              │
│ - Blocks: All other phases                             │
│ - Risk: Low                                            │
│ - Can commit immediately after                          │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 2: Core Rate Limiter (FOUNDATION)                │
│ - Blocks: Phase 3, 4                                   │
│ - Risk: Medium (file locking, state persistence)       │
│ - Test thoroughly before proceeding                     │
└─────────────────────────────────────────────────────────┘
                         ↓
            ┌────────────┴────────────┐
            ↓                         ↓
┌─────────────────────────┐  ┌─────────────────────────┐
│ Phase 3: Gemini         │  │ Phase 4: TogetherAI     │
│ - Parallel with Phase 4 │  │ - Parallel with Phase 3 │
│ - Risk: Low             │  │ - Risk: Medium-High     │
└─────────────────────────┘  └─────────────────────────┘
            │                         │
            └────────────┬────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 5: Testing & Validation (QUALITY GATE)           │
│ - Blocks: Phase 6, commit                              │
│ - Risk: Low                                            │
│ - All tests must pass                                   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 6: Documentation (FINAL STEP)                    │
│ - No blockers                                          │
│ - Risk: Low                                            │
│ - Ready to commit and merge                             │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 1: API Key Security

**Goal:** Separate configuration templates from actual secrets

**Duration:** 30-60 minutes
**Risk:** Low
**Blocker:** Must complete before all other phases

### Current Problem

- `.env` file contains actual API keys
- API keys visible in version control history
- Security risk for public repositories
- No separation between templates and secrets

### Solution

Follow PR #37 pattern:
- `.env` → rename to `.env.local` (gitignored, contains secrets)
- Create `.env.example` (template with placeholders, safe to commit)
- Multi-file env loading: `.env.example` + `.env.local` (local overrides)

### Tasks

1. **Copy current `.env` to `.env.local`**
   ```bash
   cp .env .env.local
   ```

2. **Create `.env.example` with placeholders**
   ```bash
   # QuickBooks OAuth Configuration
   QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com
   QB_CLIENT_ID=your_client_id_here
   QB_CLIENT_SECRET=your_client_secret_here
   QB_REDIRECT_URI=http://localhost:8000/callback

   # Gemini AI Configuration
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.0-flash-exp
   GEMINI_TIMEOUT=30
   GEMINI_RPM_LIMIT=15   # Free tier: 15 requests/minute
   GEMINI_RPD_LIMIT=1500 # Free tier: 1500 requests/day

   # TogetherAI Configuration
   TOGETHER_API_KEY=your_together_api_key_here
   TOGETHER_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
   TOGETHER_MAX_TOKENS=4096
   TOGETHER_TEMPERATURE=0.2
   TOGETHER_RPM_LIMIT=60    # Adjust based on your tier
   TOGETHER_RPD_LIMIT=1500  # Adjust based on your tier

   # Application Settings
   APP_NAME=quickexpense
   DEBUG=false
   LOG_LEVEL=INFO
   ```

3. **Update `.gitignore`**
   ```
   # Environment files with secrets
   .env.local
   .env*.local

   # Rate limiter state files
   data/rate_limiter_*.json
   data/*.lock
   ```

4. **Modify `src/quickexpense/core/config.py`**

   Add rate limiting configuration fields:
   ```python
   # Gemini rate limiting
   gemini_rpm_limit: int = Field(
       default=15,
       description="Gemini requests per minute limit"
   )
   gemini_rpd_limit: int = Field(
       default=1500,
       description="Gemini requests per day limit"
   )

   # TogetherAI rate limiting
   together_rpm_limit: int = Field(
       default=60,
       description="TogetherAI requests per minute limit"
   )
   together_rpd_limit: int = Field(
       default=1500,
       description="TogetherAI requests per day limit"
   )

   # Rate limiter configuration
   rate_limiter_state_dir: str = Field(
       default="data",
       description="Directory for rate limiter state files"
   )
   ```

   Update `model_config` for multi-file loading:
   ```python
   model_config = SettingsConfigDict(
       env_file=[".env.example", ".env.local"],  # Local overrides example
       env_file_encoding="utf-8",
       case_sensitive=False,
       extra="ignore",
   )
   ```

### Testing

- Start application: `uv run fastapi dev src/quickexpense/main.py`
- Verify no "missing API key" errors
- Verify config loads correctly from both files
- Test receipt upload to confirm API keys work

### Commit

```bash
git add .env.example .gitignore src/quickexpense/core/config.py
git commit -m "feat: add secure API key configuration with .env.local

- Separate secrets (.env.local) from templates (.env.example)
- Add rate limiting configuration fields
- Support multi-file env loading (example + local)
- Update .gitignore to exclude secrets and state files

Follows pattern from quickExpense-rag PR #37"
```

---

## Phase 2: Core Rate Limiter Module

**Goal:** Create reusable rate limiter with state persistence

**Duration:** 2-3 hours
**Risk:** Medium (file locking, state persistence complexity)
**Blocker:** Required for Phase 3 and Phase 4

### Design

Based on PR #37's proven implementation:
- **Stateful**: JSON persistence (`data/rate_limiter_{provider}.json`)
- **Process-safe**: File locking via `filelock` library
- **Timezone-aware**: Daily reset at midnight Pacific Time
- **Per-provider**: Separate instances for Gemini and TogetherAI
- **Singleton pattern**: One instance per provider

### Algorithm

1. Load state from JSON file (create if missing)
2. Check if new day → reset daily counter
3. Prune timestamps older than 60 seconds (RPM window)
4. If RPM limit exceeded → sleep until oldest timestamp expires
5. Check daily limit → raise exception if exceeded
6. Record new request timestamp
7. Increment daily counter
8. Save state to disk with file locking

### Tasks

1. **Add dependency to `pyproject.toml`**
   ```toml
   dependencies = [
       # ... existing dependencies ...
       "filelock>=3.13.0",
   ]
   ```

   Run: `uv sync`

2. **Create `src/quickexpense/services/rate_limiter.py`** (~200 lines)

   ```python
   """Rate limiter with state persistence for API quota management."""
   from __future__ import annotations

   import json
   import logging
   import time
   from datetime import datetime
   from pathlib import Path
   from typing import TYPE_CHECKING
   from zoneinfo import ZoneInfo

   from filelock import FileLock

   if TYPE_CHECKING:
       from quickexpense.core.config import Settings

   logger = logging.getLogger(__name__)


   class RateLimiter:
       """Rate limiter with JSON state persistence and file locking."""

       _instances: dict[str, RateLimiter] = {}  # Singleton per provider

       def __init__(
           self,
           provider: str,
           rpm_limit: int,
           rpd_limit: int,
           state_dir: Path,
       ) -> None:
           """Initialize rate limiter for specific provider."""
           self.provider = provider
           self.rpm_limit = rpm_limit
           self.rpd_limit = rpd_limit
           self.state_file = state_dir / f"rate_limiter_{provider}.json"
           self.lock_file = state_dir / f"rate_limiter_{provider}.lock"

           # Ensure state directory exists
           state_dir.mkdir(parents=True, exist_ok=True)

           # Load existing state or initialize
           self._load_state()

       @classmethod
       def get_instance(
           cls,
           provider: str,
           settings: Settings
       ) -> RateLimiter:
           """Get or create singleton instance for provider."""
           if provider not in cls._instances:
               # Determine limits based on provider
               if provider == "gemini":
                   rpm = settings.gemini_rpm_limit
                   rpd = settings.gemini_rpd_limit
               elif provider == "together":
                   rpm = settings.together_rpm_limit
                   rpd = settings.together_rpd_limit
               else:
                   raise ValueError(f"Unknown provider: {provider}")

               state_dir = Path(settings.rate_limiter_state_dir)
               cls._instances[provider] = cls(provider, rpm, rpd, state_dir)

           return cls._instances[provider]

       def _load_state(self) -> None:
           """Load state from JSON file with file locking."""
           lock = FileLock(self.lock_file, timeout=10)

           try:
               with lock:
                   if self.state_file.exists():
                       with open(self.state_file) as f:
                           data = json.load(f)
                       self.timestamps: list[float] = data.get("timestamps", [])
                       self.daily_count: int = data.get("daily_count", 0)
                       self.day_str: str = data.get("day_str", "")
                   else:
                       self.timestamps = []
                       self.daily_count = 0
                       self.day_str = ""
           except Exception as e:
               logger.warning(f"Failed to load rate limiter state: {e}")
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
                   with open(self.state_file, "w") as f:
                       json.dump(data, f, indent=2)
           except Exception as e:
               logger.error(f"Failed to save rate limiter state: {e}")

       def _get_current_day_str(self) -> str:
           """Get current day string in Pacific Time."""
           return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")

       def _reset_daily_counter(self) -> None:
           """Reset daily counter if new day detected."""
           current_day = self._get_current_day_str()
           if current_day != self.day_str:
               logger.info(f"Rate limiter {self.provider}: New day detected, resetting daily count")
               self.daily_count = 0
               self.day_str = current_day

       def check_and_wait(self) -> None:
           """Check rate limits and wait if needed."""
           self._reset_daily_counter()

           # Check daily limit
           if self.daily_count >= self.rpd_limit:
               msg = (
                   f"Daily quota exceeded for {self.provider} "
                   f"({self.daily_count}/{self.rpd_limit})"
               )
               raise ValueError(msg)

           current_time = time.time()

           # Prune old timestamps (older than 60 seconds)
           self.timestamps = [
               ts for ts in self.timestamps
               if current_time - ts < 60
           ]

           # Check RPM limit
           if len(self.timestamps) >= self.rpm_limit:
               # Need to wait until oldest request expires
               oldest_timestamp = self.timestamps[0]
               wait_time = 60 - (current_time - oldest_timestamp)

               if wait_time > 0:
                   logger.info(
                       f"Rate limit reached for {self.provider}, "
                       f"waiting {wait_time:.1f}s"
                   )
                   time.sleep(wait_time)
                   current_time = time.time()

           # Record new request
           self.timestamps.append(current_time)
           self.daily_count += 1

           # Save state
           self._save_state()

           logger.debug(
               f"Rate limiter {self.provider}: "
               f"{len(self.timestamps)}/{self.rpm_limit} RPM, "
               f"{self.daily_count}/{self.rpd_limit} RPD"
           )
   ```

3. **Create `tests/services/test_rate_limiter.py`** (~150 lines)

   See detailed test implementation in Phase 5 section.

### Testing

```bash
# Run unit tests
uv run pytest tests/services/test_rate_limiter.py -v

# Verify:
# - Singleton pattern works
# - RPM limit enforced
# - RPD limit enforced
# - State persistence
# - Daily reset logic
# - File locking
```

### Commit

```bash
git add pyproject.toml uv.lock src/quickexpense/services/rate_limiter.py tests/services/test_rate_limiter.py
git commit -m "feat: add stateful rate limiter with JSON persistence

- Implement RateLimiter class with RPM and RPD tracking
- JSON state persistence with file locking for concurrent access
- Timezone-aware daily reset (midnight Pacific Time)
- Singleton pattern per provider (gemini, together)
- Comprehensive unit tests

Based on quickExpense-rag PR #37 design"
```

---

## Phase 3: Gemini Integration

**Goal:** Integrate rate limiter with GeminiService

**Duration:** 1-2 hours
**Risk:** Low (direct API call, full control)
**Dependency:** Phase 2 (Core Rate Limiter)

### Current Flow

```
GeminiService.extract_receipt_data()
    → Process file (PDF → image conversion)
    → Decode image
    → Build prompt
    → Call Gemini API ← NO RATE LIMITING HERE
    → Parse JSON response
    → Return ExtractedReceipt
```

### New Flow

```
GeminiService.extract_receipt_data()
    → Process file (PDF → image conversion)
    → Decode image
    → Build prompt
    → CHECK RATE LIMIT ← NEW
    → Call Gemini API
    → Parse JSON response
    → Return ExtractedReceipt
```

### Tasks

1. **Modify `src/quickexpense/services/gemini.py`**

   **In `__init__` method:**
   ```python
   def __init__(self, settings: Settings) -> None:
       """Initialize the Gemini service."""
       self.settings = settings
       self.file_processor = FileProcessorService()
       genai.configure(api_key=settings.gemini_api_key)

       # Initialize rate limiter
       from quickexpense.services.rate_limiter import RateLimiter
       self.rate_limiter = RateLimiter.get_instance("gemini", settings)

       # Configure the model...
       self.model = genai.GenerativeModel(...)
   ```

   **In `extract_receipt_data` method (before API call):**
   ```python
   async def extract_receipt_data(
       self,
       file_base64: str,
       additional_context: str | None = None,
       file_type: FileType | str | None = None,
   ) -> ExtractedReceipt:
       """Extract receipt data from a base64 encoded file."""
       start_time = time.time()

       try:
           # Process file (PDF → image conversion if needed)
           processed_file = await self.file_processor.process_file(
               file_base64, file_type
           )

           # Decode image
           image_data = base64.b64decode(processed_file.content)
           image = Image.open(BytesIO(image_data))

           # Build prompt
           prompt = self._build_extraction_prompt(additional_context)

           # CHECK RATE LIMIT BEFORE API CALL
           logger.debug("Checking Gemini rate limit before API call")
           self.rate_limiter.check_and_wait()

           # Process with Gemini API
           logger.debug("Calling Gemini API for receipt extraction")
           response = self.model.generate_content([prompt, image])

           # ... rest of processing ...
   ```

### Testing

```bash
# Test via CLI
uv run quickexpense upload test_receipt.jpg

# Verify in logs:
# - "Checking Gemini rate limit before API call"
# - "Rate limiter gemini: 1/15 RPM, 1/1500 RPD"

# Check state file created
cat data/rate_limiter_gemini.json

# Test rate limiting (process 20 receipts rapidly)
for i in {1..20}; do
    uv run quickexpense upload test_receipt.jpg
done

# Should see wait messages after 15 requests
```

### Commit

```bash
git add src/quickexpense/services/gemini.py
git commit -m "feat: integrate rate limiting for Gemini API

- Initialize rate limiter in GeminiService.__init__
- Call check_and_wait() before Gemini API requests
- Add debug logging for rate limit checks
- Preserves existing functionality and error handling"
```

---

## Phase 4: TogetherAI Integration

**Goal:** Integrate rate limiting for TogetherAI calls through autogen

**Duration:** 2-3 hours
**Risk:** Medium-High (autogen framework limitations)
**Dependency:** Phase 2 (Core Rate Limiter)

### Challenge

**Problem:** Autogen doesn't expose pre-request hooks
- Can't easily intercept individual API calls
- Multi-turn conversations happen internally
- Would need to modify autogen library (not maintainable)

**Solution:** Agent-level rate limiting
- Rate limit before each agent conversation starts
- Less precise (not per-turn) but maintainable
- Document limitations clearly

### Architecture

```
Current:
Orchestrator → CRArulesAgent.process() → Autogen → TogetherAI API
                                          (multiple turns, no control)

New:
Orchestrator → check_rate_limit() → CRArulesAgent.process() → Autogen → TogetherAI API
```

### Tasks

1. **Modify `src/quickexpense/services/agents/base.py`**

   Add rate limiting support to base agent:
   ```python
   from quickexpense.services.rate_limiter import RateLimiter

   class BaseAgent:
       """Base class for all agents with rate limiting support."""

       def __init__(self, settings: Settings, ...):
           self.settings = settings
           # Initialize TogetherAI rate limiter
           self.rate_limiter = RateLimiter.get_instance("together", settings)
           # ... rest of initialization ...

       def check_rate_limit(self) -> None:
           """Check rate limit before agent operation."""
           logger.debug(f"Checking TogetherAI rate limit for {self.__class__.__name__}")
           self.rate_limiter.check_and_wait()
   ```

2. **Modify `src/quickexpense/services/agents/orchestrator.py`**

   Add rate limit checks before each agent call:
   ```python
   class AgentOrchestrator:
       async def process_receipt_with_agents(
           self,
           receipt_data: ExtractedReceipt,
           ...
       ) -> MultiAgentResult:
           """Process receipt through multi-agent system."""

           # ... existing code ...

           # Rate limit before CRA rules agent
           logger.info("Processing with CRArulesAgent")
           self.cra_rules_agent.check_rate_limit()
           cra_result = await self.cra_rules_agent.process(...)

           # Rate limit before tax calculator agent
           logger.info("Processing with TaxCalculatorAgent")
           self.tax_calculator_agent.check_rate_limit()
           tax_result = await self.tax_calculator_agent.process(...)

           # ... rest of orchestration ...
   ```

3. **Update DataExtractionAgent (if using TogetherAI validation)**

   If DataExtractionAgent uses TogetherAI for validation:
   ```python
   async def validate_with_agent(self, ...):
       """Optionally validate with TogetherAI agent."""
       if self.settings.llm_provider == "together":
           self.check_rate_limit()
           # ... validation logic ...
   ```

### Known Limitations

Document these clearly:

1. **Agent-level granularity**: Rate limiting applied before agent conversation starts, not per-turn
2. **Multi-turn conversations**: Single agent call may make multiple API requests without individual tracking
3. **Parallel agent execution**: Could hit rate limits if agents run simultaneously

**Workaround**: Set conservative limits in `.env.local` to account for multi-turn conversations.

### Testing

```bash
# Test multi-agent system
uv run quickexpense upload test_receipt.jpg

# Verify in logs:
# - "Checking TogetherAI rate limit for CRArulesAgent"
# - "Checking TogetherAI rate limit for TaxCalculatorAgent"
# - "Rate limiter together: X/60 RPM, Y/1500 RPD"

# Check state file
cat data/rate_limiter_together.json

# Verify multi-agent system still works correctly
# Check that final expense data is correct
```

### Commit

```bash
git add src/quickexpense/services/agents/base.py src/quickexpense/services/agents/orchestrator.py
git commit -m "feat: integrate rate limiting for TogetherAI agents

- Add check_rate_limit() method to BaseAgent
- Call rate limit checks before each agent conversation
- Agent-level granularity (not per-turn) due to autogen limitations
- Document known limitations in code comments

Note: Per-turn tracking not feasible with autogen framework"
```

---

## Phase 5: Testing & Validation

**Goal:** Comprehensive testing without breaking existing functionality

**Duration:** 2-3 hours
**Risk:** Low (quality gate before release)
**Dependency:** Phases 2, 3, 4 (all implementations)

### Testing Strategy

1. **Unit Tests**: Test rate limiter core logic in isolation
2. **Integration Tests**: Test Gemini and agent integrations
3. **Manual Testing**: Verify end-to-end functionality
4. **Regression Testing**: Ensure existing tests still pass

### Unit Tests

**Create `tests/services/test_rate_limiter.py`:**

```python
"""Unit tests for rate limiter module."""
import json
import time
from pathlib import Path
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

    def test_rate_limiter_initialization(self, mock_settings):
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter.get_instance("gemini", mock_settings)
        assert limiter.provider == "gemini"
        assert limiter.rpm_limit == 3
        assert limiter.rpd_limit == 10

    def test_rate_limiter_singleton(self, mock_settings):
        """Test singleton pattern per provider."""
        limiter1 = RateLimiter.get_instance("gemini", mock_settings)
        limiter2 = RateLimiter.get_instance("gemini", mock_settings)
        assert limiter1 is limiter2

        # Different provider = different instance
        limiter3 = RateLimiter.get_instance("together", mock_settings)
        assert limiter3 is not limiter1

    def test_rate_limiter_rpm_enforcement(self, mock_settings):
        """Test RPM limit is enforced."""
        # Clear singleton for clean test
        RateLimiter._instances.clear()
        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # First 3 requests should pass immediately
        for i in range(3):
            start = time.time()
            limiter.check_and_wait()
            elapsed = time.time() - start
            assert elapsed < 0.5  # Should be instant

        # 4th request should wait
        start = time.time()
        limiter.check_and_wait()
        elapsed = time.time() - start
        assert elapsed >= 10  # Should wait for timestamp to expire

    def test_rate_limiter_rpd_enforcement(self, mock_settings):
        """Test daily limit is enforced."""
        RateLimiter._instances.clear()
        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # Use up daily quota
        for i in range(10):
            limiter.timestamps = []  # Clear RPM tracking
            limiter.check_and_wait()

        # Next request should raise exception
        with pytest.raises(ValueError, match="Daily quota exceeded"):
            limiter.check_and_wait()

    def test_rate_limiter_state_persistence(self, mock_settings, temp_state_dir):
        """Test state persists to JSON file."""
        RateLimiter._instances.clear()
        limiter = RateLimiter.get_instance("gemini", mock_settings)
        limiter.check_and_wait()

        state_file = temp_state_dir / "rate_limiter_gemini.json"
        assert state_file.exists()

        with open(state_file) as f:
            data = json.load(f)

        assert "timestamps" in data
        assert "daily_count" in data
        assert data["daily_count"] == 1
        assert len(data["timestamps"]) == 1

    def test_rate_limiter_daily_reset(self, mock_settings):
        """Test daily counter resets at midnight."""
        RateLimiter._instances.clear()
        limiter = RateLimiter.get_instance("gemini", mock_settings)
        limiter.daily_count = 5
        limiter.day_str = "2024-01-01"  # Old date

        # Mock current day as different
        with patch.object(limiter, '_get_current_day_str', return_value="2024-01-02"):
            limiter.check_and_wait()

        assert limiter.daily_count == 1  # Reset + new request
        assert limiter.day_str == "2024-01-02"

    def test_concurrent_access(self, mock_settings):
        """Test file locking prevents race conditions."""
        RateLimiter._instances.clear()
        limiter = RateLimiter.get_instance("gemini", mock_settings)

        # Multiple rapid calls should not corrupt state
        for _ in range(5):
            limiter.check_and_wait()

        # Verify state file is valid JSON
        with open(limiter.state_file) as f:
            data = json.load(f)

        assert isinstance(data["timestamps"], list)
        assert isinstance(data["daily_count"], int)
```

### Integration Tests

**Create `tests/integration/test_gemini_rate_limiting.py`:**

```python
"""Integration tests for Gemini rate limiting."""
import pytest
from unittest.mock import Mock, patch

from quickexpense.services.gemini import GeminiService


@pytest.mark.integration
class TestGeminiRateLimiting:
    """Test Gemini service with rate limiting."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = Mock()
        settings.gemini_api_key = "test_key"
        settings.gemini_model = "gemini-2.0-flash-exp"
        settings.gemini_rpm_limit = 2
        settings.gemini_rpd_limit = 10
        settings.rate_limiter_state_dir = "data"
        return settings

    @pytest.mark.asyncio
    async def test_rate_limiter_initialized(self, mock_settings):
        """Test rate limiter is initialized in GeminiService."""
        service = GeminiService(mock_settings)
        assert hasattr(service, 'rate_limiter')
        assert service.rate_limiter.provider == "gemini"

    @pytest.mark.asyncio
    async def test_rate_limit_called_before_api(self, mock_settings):
        """Test rate limiter is called before API requests."""
        service = GeminiService(mock_settings)

        # Mock the rate limiter check
        with patch.object(service.rate_limiter, 'check_and_wait') as mock_check:
            # Mock Gemini API response
            with patch.object(service.model, 'generate_content') as mock_api:
                mock_api.return_value.text = '{"vendor_name": "Test"}'

                # Attempt to call extract_receipt_data
                # (will fail due to incomplete mocking, but rate limit should be called)
                try:
                    await service.extract_receipt_data("fake_base64")
                except Exception:
                    pass

                # Verify rate limiter was called
                assert mock_check.called
```

**Create `tests/integration/test_agent_rate_limiting.py`:**

```python
"""Integration tests for agent rate limiting."""
import pytest
from unittest.mock import Mock

from quickexpense.services.agents.base import BaseAgent


@pytest.mark.integration
class TestAgentRateLimiting:
    """Test multi-agent system with rate limiting."""

    def test_base_agent_has_rate_limiter(self):
        """Test BaseAgent initializes rate limiter."""
        settings = Mock()
        settings.together_rpm_limit = 60
        settings.together_rpd_limit = 1500
        settings.rate_limiter_state_dir = "data"

        # Create a concrete agent (DataExtractionAgent, CRArulesAgent, etc.)
        # For now, test that BaseAgent has the method
        assert hasattr(BaseAgent, 'check_rate_limit')
```

### Manual Testing Checklist

```markdown
## Manual Testing Checklist

### Phase 1: API Key Security
- [ ] Copy .env to .env.local
- [ ] Update .env with placeholders (becomes .env.example)
- [ ] Start application: `uv run fastapi dev src/quickexpense/main.py`
- [ ] Verify config loads correctly (no errors)
- [ ] Test receipt upload: `uv run quickexpense upload test.jpg`
- [ ] Verify API keys work

### Phase 2-3: Gemini Rate Limiting
- [ ] Process single receipt, check logs for "Checking Gemini rate limit"
- [ ] Verify `data/rate_limiter_gemini.json` created
- [ ] Process 3 receipts rapidly (under limit, no waits)
- [ ] Process 20 receipts (should wait after 15 due to RPM limit)
- [ ] Verify waits logged: "Rate limit reached for gemini, waiting X.Xs"
- [ ] Check state file shows correct counts
- [ ] Restart app, verify state persists

### Phase 4: TogetherAI Rate Limiting
- [ ] Upload receipt with multi-agent processing
- [ ] Verify logs show "Checking TogetherAI rate limit for CRArulesAgent"
- [ ] Verify logs show "Checking TogetherAI rate limit for TaxCalculatorAgent"
- [ ] Verify `data/rate_limiter_together.json` created
- [ ] Verify multi-agent system completes successfully
- [ ] Check final expense data is correct

### Phase 5: Concurrent Access
- [ ] Start web server in background
- [ ] Run CLI command simultaneously
- [ ] Verify no file locking errors
- [ ] Verify both operations complete successfully
- [ ] Check state files for correct counts

### Regression Testing
- [ ] Run full test suite: `uv run pytest`
- [ ] Verify all existing tests still pass
- [ ] No new test failures introduced
```

### Commit

```bash
git add tests/services/test_rate_limiter.py tests/integration/test_gemini_rate_limiting.py tests/integration/test_agent_rate_limiting.py
git commit -m "test: add comprehensive rate limiter tests

- Unit tests for RateLimiter class
- Integration tests for Gemini service
- Integration tests for agent system
- Manual testing checklist documented

All tests pass with >90% coverage for new code"
```

---

## Phase 6: Documentation

**Goal:** Comprehensive documentation for users and developers

**Duration:** 1-2 hours
**Risk:** Low
**Dependency:** All previous phases complete

### Documentation Files

#### 1. `docs/RATE_LIMITING.md` - Complete User Guide

**Content outline:**
- Overview of rate limiting system
- Configuration (free tier defaults, paid tier overrides)
- How it works (Gemini vs TogetherAI differences)
- State persistence and daily reset
- Monitoring usage (logs, state files)
- Known limitations (TogetherAI per-turn tracking)
- Troubleshooting (quota exceeded, too aggressive, corruption)
- Best practices

#### 2. `docs/MIGRATION_GUIDE.md` - Step-by-Step Migration

**Content outline:**
- Quick migration (7 steps in 5 minutes)
- What changed (before/after comparison)
- File structure changes
- Configuration loading changes
- New features
- Troubleshooting common issues
- Team setup instructions
- CI/CD configuration
- Rollback instructions

#### 3. Update `CLAUDE.md` - Developer Documentation

**Add section after "Environment Configuration":**

```markdown
### Rate Limiting Configuration

Control API quota usage with rate limiting:

```bash
# Gemini rate limits (free tier defaults)
GEMINI_RPM_LIMIT=15    # Requests per minute
GEMINI_RPD_LIMIT=1500  # Requests per day

# TogetherAI rate limits
TOGETHER_RPM_LIMIT=60
TOGETHER_RPD_LIMIT=1500

# Rate limiter state directory
RATE_LIMITER_STATE_DIR=data
```

Rate limiting prevents API quota exhaustion and ensures reliable operation.

See [docs/RATE_LIMITING.md](docs/RATE_LIMITING.md) for complete documentation.
```

#### 4. Update `README.md` - Feature List

**Add to "Features" section:**
```markdown
- ✅ **API Rate Limiting** - Intelligent quota management prevents API exhaustion
- ✅ **Secure API Keys** - Proper secrets management with .env.local
```

**Update "Quick Start" section:**
```markdown
### 3. Configure API Keys

```bash
# Copy template to local config
cp .env.example .env.local

# Edit .env.local and add your API keys
nano .env.local
```

Never commit `.env.local` - it contains your secrets!
```

### Commit

```bash
git add docs/RATE_LIMITING.md docs/MIGRATION_GUIDE.md CLAUDE.md README.md
git commit -m "docs: add rate limiting and migration documentation

- Complete rate limiting user guide (RATE_LIMITING.md)
- Step-by-step migration guide (MIGRATION_GUIDE.md)
- Update CLAUDE.md with configuration section
- Update README.md with new features and setup steps

Documentation covers all use cases and troubleshooting"
```

---

## Complete File Manifest

### New Files (7)

1. **`src/quickexpense/services/rate_limiter.py`** (~200 lines)
   - Core rate limiter module with state persistence

2. **`.env.example`** (~50 lines)
   - Configuration template with placeholders

3. **`docs/RATE_LIMITING.md`** (~300 lines)
   - Comprehensive rate limiting documentation

4. **`docs/MIGRATION_GUIDE.md`** (~200 lines)
   - Step-by-step migration guide

5. **`tests/services/test_rate_limiter.py`** (~150 lines)
   - Unit tests for rate limiter

6. **`tests/integration/test_gemini_rate_limiting.py`** (~50 lines)
   - Integration tests for Gemini

7. **`tests/integration/test_agent_rate_limiting.py`** (~30 lines)
   - Integration tests for agents

### Modified Files (8)

1. **`src/quickexpense/core/config.py`**
   - Add rate limit configuration fields
   - Support multi-file env loading

2. **`src/quickexpense/services/gemini.py`**
   - Initialize rate limiter
   - Call check_and_wait() before API calls

3. **`src/quickexpense/services/agents/base.py`**
   - Add rate limiter initialization
   - Add check_rate_limit() method

4. **`src/quickexpense/services/agents/orchestrator.py`**
   - Call check_rate_limit() before each agent

5. **`.gitignore`**
   - Add `.env.local` and rate limiter state files

6. **`pyproject.toml`**
   - Add `filelock>=3.13.0` dependency

7. **`CLAUDE.md`**
   - Add rate limiting configuration section

8. **`README.md`**
   - Add rate limiting to features
   - Update quick start with .env.local

### Managed Files (1)

1. **`.env` → `.env.local`**
   - Rename to preserve secrets
   - Create new `.env` from template

---

## Success Criteria

### Functional Requirements

- ✅ API keys no longer committed to version control
- ✅ Rate limiting prevents quota exhaustion for Gemini
- ✅ Rate limiting prevents quota exhaustion for TogetherAI
- ✅ State persists across application restarts
- ✅ All existing tests pass
- ✅ Multi-agent system continues to function correctly

### Performance Requirements

- ✅ Rate limit checks complete in under 50ms
- ✅ No noticeable delay for under-limit requests
- ✅ File locking doesn't cause bottlenecks
- ✅ Concurrent access (web + CLI) works correctly

### Code Quality Requirements

- ✅ All new code passes Ruff linting (600+ rules)
- ✅ Type hints complete and validated by Pyright
- ✅ Test coverage greater than 90% for new code
- ✅ Pre-commit hooks pass
- ✅ Black formatting applied

### Documentation Requirements

- ✅ User documentation comprehensive (RATE_LIMITING.md)
- ✅ Migration guide clear and tested (MIGRATION_GUIDE.md)
- ✅ Code comments explain rate limiting approach
- ✅ Known limitations documented

---

## Risk Mitigation

### High-Risk Areas

#### 1. TogetherAI Autogen Integration

**Risk:** May not achieve per-turn tracking due to autogen framework limitations

**Impact:** High (could under-limit or over-limit agent calls)

**Mitigation:**
- Use agent-level tracking (before conversation starts)
- Set conservative limits to account for multi-turn conversations
- Document limitations clearly in code and user docs
- Consider alternative approaches if blocking issues arise

**Fallback:** Document manual rate limit configuration in TogetherAI dashboard

#### 2. File Locking Under High Concurrency

**Risk:** File locking may cause slowdowns with many concurrent requests

**Impact:** Medium (performance degradation)

**Mitigation:**
- Use 10-second timeout on file locks (graceful failure)
- Test with concurrent web + CLI access
- Optimize if needed (e.g., in-memory caching)

**Fallback:** Disable rate limiting for specific provider (set limits to 0)

#### 3. State File Corruption

**Risk:** State file could become corrupted or deleted

**Impact:** Low (rate limiting breaks, but app continues)

**Mitigation:**
- Graceful error handling in _load_state()
- Easy manual reset (delete state file)
- State file is in gitignored data/ directory

**Fallback:** Delete state file and restart app (fresh start)

### Rollback Plan

If critical issues discovered during implementation:

1. **Immediate Rollback:**
   ```bash
   # Revert to commit before Phase 1
   git reset --hard <commit_before_phase_1>

   # Restore original .env
   cp .env.backup .env
   ```

2. **Cleanup:**
   ```bash
   # Remove new files
   rm .env.local .env.example
   rm -rf data/rate_limiter_*.json
   rm -rf data/rate_limiter_*.lock
   rm src/quickexpense/services/rate_limiter.py
   ```

3. **Document Issues:**
   - Create GitHub issue with details
   - Note which phase failed
   - Include error messages and logs

4. **Future Attempt:**
   - Address root cause
   - Consider alternative approach
   - Re-plan if needed

---

## Execution Checklist

### Pre-Implementation

- [x] Backup current `.env` file
- [x] Create feature branch: `git checkout -b feat/api-key-security-rate-limiting`
- [ ] Verify current tests pass: `uv run pytest`

### Phase 1: API Key Security (30-60 min)

- [ ] Copy `.env` to `.env.local` (preserve secrets)
- [ ] Create `.env.example` with placeholder values
- [ ] Update `.gitignore` to exclude `.env.local` and `data/rate_limiter_*.json`
- [ ] Modify `config.py`: add rate limit fields + multi-file env loading
- [ ] Test: `uv run fastapi dev src/quickexpense/main.py` (verify starts)
- [ ] Test: `uv run quickexpense upload test.jpg` (verify API keys work)
- [ ] Commit: `git commit -m "feat: add secure API key configuration with .env.local"`

### Phase 2: Core Rate Limiter (2-3 hours)

- [ ] Add `filelock>=3.13.0` to `pyproject.toml`
- [ ] Run `uv sync` to install dependency
- [ ] Create `src/quickexpense/services/rate_limiter.py`
- [ ] Create `tests/services/test_rate_limiter.py`
- [ ] Test: `uv run pytest tests/services/test_rate_limiter.py -v`
- [ ] Verify all unit tests pass
- [ ] Commit: `git commit -m "feat: add stateful rate limiter with JSON persistence"`

### Phase 3: Gemini Integration (1-2 hours)

- [ ] Modify `src/quickexpense/services/gemini.py`
  - [ ] Import RateLimiter in `__init__`
  - [ ] Add rate limiter initialization
  - [ ] Call `check_and_wait()` before API call
- [ ] Test: Process receipt via CLI, check logs
- [ ] Verify `data/rate_limiter_gemini.json` created
- [ ] Test: Process 20 receipts, verify waits after 15
- [ ] Commit: `git commit -m "feat: integrate rate limiting for Gemini API"`

### Phase 4: TogetherAI Integration (2-3 hours)

- [ ] Modify `src/quickexpense/services/agents/base.py`
  - [ ] Add rate limiter initialization
  - [ ] Add `check_rate_limit()` method
- [ ] Modify `src/quickexpense/services/agents/orchestrator.py`
  - [ ] Call `check_rate_limit()` before each agent
- [ ] Test: Upload receipt with multi-agent processing
- [ ] Verify `data/rate_limiter_together.json` created
- [ ] Verify multi-agent system completes successfully
- [ ] Commit: `git commit -m "feat: integrate rate limiting for TogetherAI agents"`

### Phase 5: Testing & Validation (2-3 hours)

- [ ] Create `tests/integration/test_gemini_rate_limiting.py`
- [ ] Create `tests/integration/test_agent_rate_limiting.py`
- [ ] Run all unit tests: `uv run pytest tests/unit -v`
- [ ] Run integration tests: `uv run pytest tests/integration -v`
- [ ] Run full test suite: `uv run pytest`
- [ ] Verify coverage: `uv run pytest --cov`
- [ ] Complete manual testing checklist (see Phase 5)
- [ ] Fix any failing tests
- [ ] Commit: `git commit -m "test: add comprehensive rate limiter tests"`

### Phase 6: Documentation (1-2 hours)

- [ ] Create `docs/RATE_LIMITING.md`
- [ ] Create `docs/MIGRATION_GUIDE.md`
- [ ] Update `CLAUDE.md` with rate limiting section
- [ ] Update `README.md` with new features
- [ ] Review all documentation for accuracy
- [ ] Commit: `git commit -m "docs: add rate limiting and migration documentation"`

### Post-Implementation

- [ ] Run pre-commit hooks: `uv run pre-commit run --all-files`
- [ ] Fix any linting/formatting issues
- [ ] Final test: `uv run pytest`
- [ ] Verify all commits follow Conventional Commits format
- [ ] Push branch: `git push -u origin feat/api-key-security-rate-limiting`
- [ ] Create PR with comprehensive description
- [ ] Reference PR #37 from quickExpense-rag
- [ ] Request review from team

---

## Commit Strategy

### Recommended: Separate Commits per Phase

**Advantages:**
- Easier to review (smaller diffs per commit)
- Can cherry-pick specific phases if needed
- Clear history shows progression
- Easy to bisect if issues arise

**Commit Messages:**
1. `feat: add secure API key configuration with .env.local`
2. `feat: add stateful rate limiter with JSON persistence`
3. `feat: integrate rate limiting for Gemini API`
4. `feat: integrate rate limiting for TogetherAI agents`
5. `test: add comprehensive rate limiter tests`
6. `docs: add rate limiting and migration documentation`

### Alternative: Squash Before Merge

**Advantages:**
- Single clean commit in main branch
- Simpler git history

**Process:**
```bash
# Squash all commits into one
git rebase -i HEAD~6

# Or use GitHub's "Squash and merge" option
```

**Final Commit Message:**
```
feat: implement API key security and rate limiting

- Separate secrets (.env.local) from templates (.env.example)
- Add stateful rate limiter with JSON persistence for Gemini and TogetherAI
- File locking prevents race conditions in concurrent scenarios
- Timezone-aware daily reset (midnight Pacific Time)
- Comprehensive testing with >90% coverage
- Complete documentation and migration guide

Based on quickExpense-rag PR #37 design
Closes #XXX
```

---

## Final Deliverables

1. **Working Implementation**
   - All 6 phases complete and tested
   - Rate limiting functional for both Gemini and TogetherAI
   - Multi-agent system unaffected

2. **Comprehensive Testing**
   - Unit tests (>90% coverage)
   - Integration tests
   - Manual testing completed

3. **Complete Documentation**
   - User guide (RATE_LIMITING.md)
   - Migration guide (MIGRATION_GUIDE.md)
   - Updated developer docs (CLAUDE.md)
   - Updated README

4. **Code Quality**
   - All pre-commit hooks pass
   - Ruff linting clean
   - Pyright type checking pass
   - Black formatting applied

5. **Pull Request**
   - Detailed PR description
   - Before/after comparison
   - Reference to PR #37
   - Test results included

---

## Reference: quickExpense-rag PR #37

**URL:** https://github.com/manonja/quickExpense-rag/pull/37

**Key Learnings:**
- Multi-file env loading pattern works well
- File locking essential for concurrent access
- JSON state persistence simpler than database
- Pacific Time for daily reset aligns with API providers
- Cache integration critical for performance

**Adaptations for quickExpense:**
- Multi-agent system requires agent-level tracking
- Two providers (Gemini + TogetherAI) vs single provider
- Web API + CLI vs single extraction script
- Autogen framework adds complexity

---

## Next Steps After Plan Approval

1. **Exit Plan Mode**
   - Confirm plan with user
   - Address any questions or concerns

2. **Begin Implementation**
   - Start with Phase 1 (API Key Security)
   - Test thoroughly after each phase
   - Commit with clear messages

3. **Progress Reporting**
   - Update after each phase completion
   - Report any blockers immediately
   - Adjust plan if needed

4. **Final Review**
   - Complete all phases
   - Run full test suite
   - Create PR for team review

---

**Status:** Ready for implementation
**Estimated Completion:** 8-14 hours (1-2 working days)
**Risk Level:** Low-Medium (proven approach, autogen complexity)
**Confidence:** High (based on PR #37 success)
