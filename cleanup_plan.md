# QuickExpense Legacy Files Cleanup Plan

## Overview
This document outlines the plan to clean up legacy files after the successful restructuring to modern Python 3.12 standards with FastAPI. All core functionality has been moved to `src/quickexpense/`.

## Phase 1: Remove Obsolete Legacy Files (High Priority)

### Files to Remove
1. **`main.py`** - Fully replaced by `src/quickexpense/main.py`
2. **`models.py`** - Replaced by `src/quickexpense/models/expense.py` and `receipt.py`
3. **`config.py`** - Replaced by `src/quickexpense/core/config.py`
4. **`quickbooks_client.py`** - Replaced by `src/quickexpense/services/quickbooks.py`
5. **`requirements.txt`** - Replaced by `pyproject.toml` with `uv` dependency management

### Rationale
- Removes ~400 lines of duplicate code
- Eliminates confusion about which files are active
- Ensures single source of truth for all functionality

## Phase 2: Implement Robust OAuth Token Management (Critical Priority)

### Current Issue
- Access tokens expire after 60 minutes
- Refresh tokens rotate on each use and expire after 100 days of inactivity
- No automatic refresh mechanism in place

### Implementation Plan

#### 2.1 Create OAuth Service Module
Create `src/quickexpense/services/oauth.py` with:
- Token refresh logic
- Token storage/retrieval
- Automatic refresh before expiry
- Refresh token rotation handling

#### 2.2 Token Management Strategy
```python
class OAuthTokenManager:
    """Handles OAuth token lifecycle management."""

    async def refresh_access_token(self) -> TokenResponse:
        """Refresh access token using current refresh token."""
        # POST to https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer
        # Update both access and refresh tokens
        # Store new tokens securely

    async def get_valid_access_token(self) -> str:
        """Get current access token, refreshing if needed."""
        # Check if current token is expired
        # If expired or close to expiry (5 min buffer), refresh
        # Return valid access token

    async def schedule_token_refresh(self):
        """Background task to refresh tokens proactively."""
        # Run every 50 minutes for access token
        # Ensure refresh token is used at least once per week
```

#### 2.3 Integration Points
- Update `QuickBooksClient` to use `OAuthTokenManager`
- Add token refresh middleware to handle 401 responses
- Implement secure token storage (environment variables or secure vault)

#### 2.4 OAuth Setup Tool Enhancement
Transform `oauth_setup.py` into a proper tool:
- Move to `tools/oauth_setup.py`
- Remove hardcoded credentials
- Add environment variable support
- Include token persistence mechanism
- Add user-friendly CLI interface

### Security Considerations
- Never commit tokens to version control
- Use secure storage for tokens (e.g., encrypted file, environment variables)
- Implement token encryption at rest
- Add logging for token refresh events

## Phase 3: Update Documentation (High Priority)

### 3.1 Rewrite README.md
Update to reflect:
- New project structure (`src/quickexpense/`)
- Modern development workflow with `uv`
- Updated API endpoints including Gemini receipt extraction
- OAuth setup instructions
- Token management guidelines
- Remove all references to legacy files

### 3.2 Update CLAUDE.md
Add sections for:
- OAuth token management
- Background task configuration
- Security best practices
- Token refresh automation

### 3.3 Create OAUTH_GUIDE.md
Comprehensive guide covering:
- Initial OAuth setup
- Token refresh automation
- Troubleshooting token issues
- Security best practices

## Phase 4: Clean Supporting Files (Low Priority)

### 4.1 Evaluate README_files/
- Check if generated documentation files are needed
- Remove if not actively used
- Add to `.gitignore` if regenerated

### 4.2 Update README_OAUTH.md
- Keep as reference for OAuth implementation
- Update with new token refresh strategy
- Move to `docs/` directory

## Phase 5: Testing and Validation (Critical Priority)

### 5.1 Pre-Cleanup Testing
Before removing files:
- Run all existing tests
- Test each API endpoint manually
- Document current working state

### 5.2 Post-Cleanup Testing
After cleanup:
- Verify all imports resolve correctly
- Run full test suite
- Test OAuth flow end-to-end
- Verify token refresh mechanism
- Test Gemini receipt extraction
- Validate QuickBooks expense creation

### 5.3 Integration Testing
- Test complete flow: Receipt → Extraction → Expense Creation
- Verify token refresh during long-running operations
- Test error handling for expired tokens

## Phase 6: Commit Strategy

### 6.1 Commit Order
1. `feat: implement OAuth token refresh automation`
2. `chore: remove legacy Python files from root`
3. `docs: update README for new project structure`
4. `chore: organize OAuth setup tool`
5. `test: add OAuth token refresh tests`

### 6.2 Git Commands
```bash
# Phase 1: Remove legacy files
git rm main.py models.py config.py quickbooks_client.py requirements.txt

# Phase 2: Add OAuth implementation
git add src/quickexpense/services/oauth.py
git add tools/oauth_setup.py

# Phase 3: Update documentation
git add README.md CLAUDE.md docs/OAUTH_GUIDE.md

# Commit with conventional commits
git commit -m "chore: remove legacy files after restructuring"
```

## Success Criteria
- [ ] All legacy files removed
- [ ] OAuth token refresh working automatically
- [ ] No broken imports or references
- [ ] All tests passing
- [ ] Documentation updated and accurate
- [ ] Application fully functional with new structure

## Risk Mitigation
- Create backup branch before cleanup
- Test incrementally after each phase
- Keep `oauth_setup.py` functionality until OAuth service is proven
- Document any discovered dependencies during cleanup

## Next Steps After Cleanup
1. Implement comprehensive logging
2. Add monitoring for token refresh events
3. Create admin dashboard for OAuth status
4. Implement webhook support for QuickBooks events
5. Add batch receipt processing
