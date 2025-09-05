# QuickBooks OAuth Test Suite

## Overview

Comprehensive test suite for QuickBooks OAuth implementation covering models, service, and integration with the QuickBooks client.

## Test Files

### 1. `test_quickbooks_oauth_models.py`
Tests for OAuth data models including:
- **QuickBooksTokenResponse**: Validates token type, converts to TokenInfo
- **QuickBooksTokenInfo**: Tests expiry checks, buffer calculations, token masking
- **QuickBooksOAuthConfig**: Tests URL generation, configuration settings

### 2. `test_quickbooks_oauth.py`
Tests for OAuth manager service including:
- **Token Management**: Initialization, validity checks, callbacks
- **Token Refresh**: Success cases, retry logic, concurrent refresh prevention
- **Error Handling**: Network failures, HTTP errors, max retries
- **OAuth Flow**: Authorization URL generation, code exchange, token revocation
- **Context Manager**: Async context manager functionality

### 3. `test_quickbooks.py`
Tests for QuickBooks client OAuth integration:
- **OAuth Integration**: Client initialization with OAuth manager
- **Token Updates**: Callback mechanism for token updates
- **401 Handling**: Automatic retry with token refresh
- **Service Methods**: Vendor management, expense creation with OAuth

## Key Test Scenarios

### Token Refresh Flow
- Tokens refresh automatically when nearing expiry (5-minute buffer)
- Concurrent refresh attempts are prevented with locking
- Failed refreshes retry up to 3 times with exponential backoff
- 401 responses trigger automatic token refresh and retry

### Error Handling
- Expired refresh tokens are detected and reported
- Network errors are retried with backoff
- Token revocation failures still clear local tokens
- Callback errors don't break the update flow

### Integration Points
- OAuth manager integrates seamlessly with QuickBooks client
- Token updates propagate to HTTP headers automatically
- Background refresh task prevents service interruption

## Running the Tests

```bash
# Run all OAuth tests
uv run pytest tests/unit/test_quickbooks_oauth_models.py tests/services/test_quickbooks_oauth.py tests/services/test_quickbooks.py -v

# Run specific test file
uv run pytest tests/services/test_quickbooks_oauth.py -v

# Run with coverage
uv run pytest tests/ -v --cov=src/quickexpense --cov-report=term-missing
```

## Test Coverage

The OAuth implementation achieves high test coverage:
- `quickbooks_oauth.py`: 86% coverage
- `quickbooks_oauth_models.py`: 100% coverage
- `quickbooks.py`: 94% coverage (OAuth-related code)

## Fixtures

Key fixtures in `conftest.py`:
- `mock_oauth_config`: OAuth configuration for testing
- `mock_token_info`: Valid token information
- `mock_oauth_manager`: Mocked OAuth manager with async support

## Future Improvements

1. Add integration tests with real QuickBooks sandbox
2. Test edge cases like clock skew
3. Add performance tests for token refresh under load
4. Test token persistence and recovery scenarios
