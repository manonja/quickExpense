# Caching Enhancement Plan

## Executive Summary
Based on expert consultation with Zen MCP and codebase analysis, implement a **3-tiered caching strategy** that prioritizes performance gains while maintaining CRA compliance and audit trail requirements.

## Current State Analysis
- ✅ **Minimal caching**: Only `@lru_cache` on settings singleton (`config.py:189`)
- ✅ **LLM caching disabled**: Intentionally set to `cache_seed: None` for consistency
- ❌ **No caching for**: Business rules (JSON/CSV loaded on every request), QuickBooks API lookups (vendors, accounts), provincial tax data

## Implementation Phases

### **Phase 1: Business Rules Caching (High Priority, Low Risk)** ✅ **COMPLETED**
**Target**: `business_rules.py` and `cra_business_rules.py`

**Changes:**
1. Load business rules once at application startup via FastAPI lifespan events
2. Store parsed rules in application state (no external dependencies needed)
3. Add optional hot-reload endpoint: `POST /api/v1/admin/reload-rules`
4. Keep existing `reload_rules()` methods for backward compatibility

**Benefits:**
- Eliminates repeated JSON/CSV parsing on every receipt
- Zero compliance risk (rules are static per application instance)
- No external dependencies (Redis, Memcached)

**Implementation:**
- Modify `main.py` lifespan to pre-load rules
- Add rules to dependency injection container
- Estimated effort: 2-3 hours

---

### **Phase 2: QuickBooks API Caching (Medium Priority, Low Risk)** ✅ **COMPLETED**
**Target**: `quickbooks.py` service methods

**What to cache:**
- `search_vendor(vendor_name)` → 10-minute TTL
- `get_expense_accounts()` → 15-minute TTL
- `get_bank_accounts()` → 15-minute TTL
- `get_credit_card_accounts()` → 15-minute TTL

**Strategy:**
- Use `cachetools` library (lightweight, no external service)
- Implement `@cached` decorator with TTLCache
- Async-compatible caching (important for FastAPI)

**Benefits:**
- Reduces QuickBooks API calls by ~70-80%
- Improves response time for receipt processing
- Stays within QuickBooks rate limits

**Audit Trail Impact:**
- ✅ **No negative impact**: Expense records store vendor/account IDs, not names
- Cache only affects lookup speed, not transaction integrity

**Implementation:**
```python
from cachetools import TTLCache, cached
from cachetools.keys import hashkey

# Vendor cache with 10-minute TTL
vendor_cache = TTLCache(maxsize=256, ttl=600)

@cached(cache=vendor_cache, key=lambda self, vendor_name: hashkey(vendor_name))
async def search_vendor(self, vendor_name: str) -> list[VendorSearchResult]:
    # Existing implementation
```

**Estimated effort:** 3-4 hours

**Implementation Details (Completed):**
- Created `src/quickexpense/core/caching.py` with async-compatible TTL cache decorator
- Created `src/quickexpense/services/quickbooks_cached.py` wrapping base QuickBooks service
- Added configuration settings to `config.py`: `enable_quickbooks_cache`, `qb_vendor_cache_ttl`, `qb_account_cache_ttl`, `qb_cache_max_size`
- Updated dependency injection in `dependencies.py` to use `CachedQuickBooksService`
- Added comprehensive unit tests in `tests/core/test_caching.py` (7 tests)
- Cache is thread-safe with asyncio locks and handles concurrent requests
- Can be disabled via settings without code changes
- Commit: `323cc8a` - "feat: implement QuickBooks API caching with TTL"

---

### **Phase 3: Receipt Idempotency Protection (Future, Requires Redis)**
**Status**: Deferred until multi-worker deployment or duplicate processing becomes an issue

**Purpose**: Prevent duplicate expense creation from same receipt
**Strategy**: Redis-based result caching with 24-hour TTL keyed by receipt content hash
**Benefits**: Idempotent processing, prevents duplicate LLM calls

**Why defer:**
- Requires Redis infrastructure (adds deployment complexity)
- Not critical for single-user prototype
- Can be added when scaling to production

---

## What NOT to Cache (Compliance Critical)

### **LLM Receipt Extraction** - KEEP DISABLED ✅
- Current: `cache_seed: None` (disabled)
- Reason: Every receipt must be auditable and reproducible
- CRA compliance requires clear lineage from image → extraction → expense

### **Tax Calculations** - DO NOT CACHE
- Provincial tax rates, GST/HST calculations must be real-time
- Regulatory changes require immediate effect

---

## Configuration Changes

### New Environment Variables (`.env`)
```bash
# Caching Configuration
ENABLE_BUSINESS_RULES_CACHE=true  # Phase 1
ENABLE_QUICKBOOKS_CACHE=true      # Phase 2
QB_VENDOR_CACHE_TTL=600           # 10 minutes
QB_ACCOUNT_CACHE_TTL=900          # 15 minutes
```

### Dependencies
```toml
# Add to pyproject.toml
cachetools = "^5.3.0"  # For Phase 2
```

---

## Testing Requirements

### Unit Tests
- `tests/services/test_business_rules_cache.py` - Verify startup loading
- `tests/services/test_quickbooks_cache.py` - Verify TTL behavior

### Integration Tests
- Test rule hot-reload endpoint
- Verify cache invalidation on TTL expiry
- Test concurrent access (async safety)

---

## Rollout Plan

1. **Week 1**: Implement Phase 1 (business rules caching)
   - Add startup loading to `main.py`
   - Test with existing receipts
   - Verify no regression in categorization

2. **Week 2**: Implement Phase 2 (QuickBooks caching)
   - Add `cachetools` dependency
   - Decorate QB service methods
   - Monitor cache hit rates

3. **Future**: Plan Phase 3 (idempotency) when scaling needs arise

---

## Success Metrics

- **Performance**: 40-60% reduction in receipt processing time
- **API Efficiency**: 70-80% fewer QuickBooks API calls
- **Compliance**: Zero impact on audit trail integrity
- **Memory**: <50MB additional memory usage for cached data

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Stale business rules | Hot-reload endpoint + clear documentation |
| Stale QB data | Short TTL (10-15 min), acceptable staleness window |
| Memory leak | Bounded caches (maxsize limits), TTL auto-expiry |
| Cache inconsistency | Single-instance deployment (no distributed cache yet) |

---

## Recommendation

**Proceed with Phase 1 and Phase 2 immediately.** These provide significant performance benefits with minimal risk and no compliance impact. Phase 3 can be deferred until production scaling requirements emerge.

---

## Implementation Notes

### Current Business Rules Loading Pattern

**`business_rules.py` (lines 64-92):**
- Loads JSON rules in `__init__` via `_load_rules()`
- Already has `reload_rules()` method for hot-reload
- Uses Pydantic models for validation

**`cra_business_rules.py` (lines 72-148):**
- Loads CSV rules using pandas in `__init__` via `_load_rules()`
- Already has `reload_rules()` method
- Converts CSV rows to Pydantic `CRARule` objects

### Dependency Injection Current State

**`core/dependencies.py`:**
- Currently provides QuickBooks service injection
- Need to add business rules engine injection
- Will cache at module level for singleton pattern

### QuickBooks Service Methods to Cache

**`services/quickbooks.py`:**
- Line 210: `async def search_vendor(self, vendor_name: str)`
- Line 236: `async def get_expense_accounts(self)`
- Line 252: `async def get_bank_accounts(self)`
- Line 268: `async def get_credit_card_accounts(self)`

---

## Technical Considerations

### Async Caching with `cachetools`

Standard `@cached` decorator doesn't work with async functions. Need to use custom wrapper:

```python
from functools import wraps
from cachetools import TTLCache
import asyncio

def async_cached(cache, key=lambda *args, **kwargs: args):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            k = key(*args, **kwargs)
            try:
                return cache[k]
            except KeyError:
                pass
            v = await func(*args, **kwargs)
            try:
                cache[k] = v
            except ValueError:
                pass  # value too large
            return v
        return wrapper
    return decorator
```

### Memory Estimates

**Business Rules:**
- JSON config: ~15KB
- CSV rules: ~8KB
- Parsed objects: ~50KB total
- **Total: <100KB**

**QuickBooks Cache:**
- Vendor cache (256 entries): ~10KB
- Account caches (3 types, ~50 entries each): ~15KB
- **Total: ~25KB**

**Combined overhead: <150KB** - negligible impact

---

## Audit Trail Preservation

### What Gets Logged (No Change)
- Expense creation with vendor ID, account ID, amounts
- Rule application with rule ID and confidence score
- Provincial detection with confidence
- LLM token usage and costs

### What Doesn't Get Logged
- Cache hits/misses (can add for monitoring)
- Lookup performance metrics (can add for monitoring)

**Conclusion**: Caching affects only lookup performance, not transaction records. Full audit trail maintained.

---

## Implementation Status Summary

### ✅ Phase 1: Business Rules Caching - COMPLETED
- **Commit**: `cd70ba7` - "feat: implement business rules caching at startup"
- **Files**: `services/rules_cache.py`, `main.py`, `dependencies.py`, `api/admin_endpoints.py`
- **Tests**: 9 tests in `tests/services/test_rules_cache.py`
- **Performance Impact**: Zero overhead after startup, eliminates repeated JSON/CSV parsing

### ✅ Phase 2: QuickBooks API Caching - COMPLETED
- **Commit**: `323cc8a` - "feat: implement QuickBooks API caching with TTL"
- **Files**: `core/caching.py`, `services/quickbooks_cached.py`, configuration updates
- **Tests**: 7 tests in `tests/core/test_caching.py`
- **Performance Impact**: Expected 70-80% reduction in QuickBooks API calls

### 🔄 Phase 3: Receipt Idempotency - DEFERRED
- **Status**: Deferred until production scaling requirements emerge
- **Reason**: Requires Redis infrastructure, not critical for single-user prototype

**Overall Impact:**
- ✅ 40-60% reduction in receipt processing time (estimated)
- ✅ Zero compliance risk - audit trail fully preserved
- ✅ Minimal memory overhead (<150KB)
- ✅ Backward compatible - can disable via configuration
